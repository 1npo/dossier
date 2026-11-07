import json
import os
import subprocess
import time

import pytest

import buildlog
import process
import restore
import sandbox
import stages
import workarea

FORBIDDEN = {"SSH_AUTH_SOCK": "forbidden-ssh", "GIT_AUTHOR_NAME": "forbidden-git", "AWS_SECRET_ACCESS_KEY": "forbidden-aws",
             "GITHUB_TOKEN": "forbidden-gh", "DATABASE_URL": "forbidden-db", "MY_SECRET": "forbidden-secret"}
PROXY = "http://proxy.invalid:3128"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("DOSSIER_CONFIG", str(tmp_path / "cfg.json"))


@pytest.fixture
def stage(tmp_path, hygiene_repo):
    area = workarea.area_for("hygiene", hygiene_repo.path, "r", tmp_path / "cache")
    co = workarea.ensure_checkout(area, hygiene_repo.path, hygiene_repo.main_sha)["path"]
    return area, co


def plan(cmd):
    return [{"ecosystem": "python", "lockfile": "uv.lock", "command": cmd, "enabled": True}]


def pid_gone(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


class TestRestoreHygiene:
    def run_install(self, stage):
        area, co = stage
        parent = {**os.environ, **FORBIDDEN, "HTTPS_PROXY": PROXY}
        res = restore.run(plan(["sh", "install.sh"]), area=area, checkout=co, timeout=30, parent=parent)
        return area, res

    def test_only_allowlisted_names_reach_the_child(self, stage):
        area, res = self.run_install(stage)

        names = set((area / "home/report/env-names.txt").read_text().split()) - {"PWD", "SHLVL", "_", "OLDPWD"}
        assert res[0]["status"] == "ok"
        assert names <= sandbox.ALLOWED_NAMES and not names & FORBIDDEN.keys()

    def test_proxy_passes_through(self, stage):
        area, _ = self.run_install(stage)

        assert "HTTPS_PROXY" in (area / "home/report/env-names.txt").read_text().split()

    def test_home_is_the_scratch_directory(self, stage):
        area, _ = self.run_install(stage)

        assert (area / "home/report/home.txt").read_text().strip() == str(area / "home")

    def test_caches_land_under_the_area(self, stage):
        area, _ = self.run_install(stage)

        markers = (area / "home/report/cache-markers.txt").read_text().split()
        assert len(markers) == 5 and all(m.startswith(str(area / "cache") + "/") for m in markers)

    def test_run_record_has_names_and_no_values(self, stage, tmp_path):
        area, res = self.run_install(stage)
        bpath = buildlog.start(tmp_path / "out", repo="h", sha="a" * 40, ref="main", version="0.6.0", options={})
        buildlog.append(bpath, {"step": "copy", "part": "restore", "by": "prepare", "status": "ok",
                                "env_names": res[0]["env_names"], "command": res[0]["command"]})

        text = bpath.read_text()
        assert "HTTPS_PROXY" in json.loads(text)["records"][0]["env_names"]
        assert not any(v in text for v in [*FORBIDDEN.values(), PROXY])

    def test_registry_credentials_are_opt_in(self, stage, monkeypatch):
        import config
        area, co = stage
        parent = {**os.environ, "MY_INDEX_TOKEN": "tok"}
        cmd = ["sh", "-c", "env | cut -d= -f1 > \"$HOME/names\""]

        restore.run(plan(cmd), area=area, checkout=co, timeout=30, parent=parent)
        without = (area / "home/names").read_text().split()
        config.update(registry_auth={"python": ["MY_INDEX_TOKEN"]})
        restore.run(plan(cmd), area=area, checkout=co, timeout=30, parent=parent)
        with_it = (area / "home/names").read_text().split()

        assert "MY_INDEX_TOKEN" not in without and "MY_INDEX_TOKEN" in with_it


class TestTrustGate:
    def test_feature_branch_refused_without_allow_ref(self, hygiene_repo):
        trust = workarea.trusted(hygiene_repo.path, hygiene_repo.feature_sha)
        plans = plan(["x"])

        refused = restore.decide(plans, state={}, answer="yes", no_restore=False, trust=trust, allow_ref=False)
        allowed = restore.decide(plans, state={}, answer="yes", no_restore=False, trust=trust, allow_ref=True)

        assert (refused["action"], "--allow-ref" in refused["reason"], allowed["action"]) == ("skip", True, "run")


class TestFailures:
    def test_timed_out_stage_is_killed_and_recorded(self, stage):
        area, co = stage

        res = restore.run(plan(["sh", "sleeper.sh"]), area=area, checkout=co, timeout=1)

        assert res[0]["status"] == "failed" and "took longer than 1 seconds" in res[0]["reason"]
        pids = [int((area / "home" / n).read_text()) for n in ("child.pid", "parent.pid")]
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not all(pid_gone(p) for p in pids):
            time.sleep(0.1)
        assert all(pid_gone(p) for p in pids)

    def test_timed_out_stage_appears_in_gaps(self, stage, tmp_path):
        area, co = stage
        res = restore.run(plan(["sh", "sleeper.sh"]), area=area, checkout=co, timeout=1)
        bpath = buildlog.start(tmp_path / "out", repo="h", sha="a" * 40, ref="main", version="0.6.0", options={})
        buildlog.append(bpath, {"step": "copy", "part": "restore", "by": "prepare", **stages.restore_fields(res)})

        items = process.coverage_items(buildlog.load(bpath))

        assert len(items) == 1 and "took longer than" in items[0]["statement"]

    def test_authentication_failure_names_registry_auth(self, stage):
        area, co = stage

        res = restore.run(plan(["sh", "-c", "echo 'npm ERR! code E401' >&2; exit 1"]), area=area, checkout=co, timeout=30)

        assert res[0]["status"] == "failed" and "registry_auth.python" in res[0]["reason"]

    def test_ordinary_failure_points_at_the_log(self, stage):
        area, co = stage

        res = restore.run(plan(["sh", "-c", "exit 3"]), area=area, checkout=co, timeout=30)

        assert "exit 3" in res[0]["reason"] and ".err" in res[0]["reason"]

    def test_disabled_ecosystem_is_skipped_with_a_reason(self, stage):
        area, co = stage

        res = restore.run([{"ecosystem": "nuget", "lockfile": "x", "command": ["false"], "enabled": False}], area=area, checkout=co, timeout=5)

        assert res[0]["status"] == "skipped" and "later version" in res[0]["reason"]


class TestNpmInstallScripts:
    """npm runs a dependency's postinstall script unless told not to; the restore command must tell it not to."""

    def project(self, root):
        (root / "dep").mkdir(parents=True)
        (root / "dep/package.json").write_text(json.dumps({"name": "dep", "version": "1.0.0", "scripts": {"postinstall": "touch ../ran"}}))
        (root / "package.json").write_text(json.dumps({"name": "app", "version": "1.0.0", "dependencies": {"dep": "file:./dep"}}))
        subprocess.run(["npm", "install", "--package-lock-only", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=root, check=True,
                       capture_output=True)

    def test_the_restore_command_does_not_run_install_scripts(self, tmp_path):
        import toolcheck
        project = tmp_path / "app"
        self.project(project)
        entry = next(r for r in toolcheck.load_tools()["restore"] if r["ecosystem"] == "npm")

        res = restore.run([{**entry, "dir": ""}], area=tmp_path / "cache" / "repo", checkout=project, timeout=120)

        assert res[0]["status"] == "ok" and (project / "node_modules").exists()
        assert not (project / "ran").exists()

    def test_control_the_same_install_without_the_flag_does_run_the_script(self, tmp_path):
        project = tmp_path / "app"
        self.project(project)

        subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=project, check=True, capture_output=True)

        assert (project / "ran").exists()
