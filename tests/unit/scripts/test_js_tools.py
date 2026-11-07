import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import js_tools
import shared_tools
import toolcheck

SCRIPTS = Path(shared_tools.__file__).parent
LOCK_DIR = SCRIPTS / "node" / "js-tools"
PACKAGES = {"dependency-cruiser": "dependency-cruiser", "knip": "knip", "scip-typescript": "@sourcegraph/scip-typescript",
            "typescript": "typescript", "yarn": "yarn", "yarn-berry": "@yarnpkg/cli-dist", "pnpm": "pnpm"}


def fake_run(tmp_path, returncode=0, timed_out=False, out="", write=None):
    calls = []

    def run(cmd, *, stage, profile, timeout, cwd=None):
        o, e = tmp_path / "o", tmp_path / "e"
        o.write_text(out)
        e.write_text("boom\nlast line")
        calls.append({"cmd": cmd, "stage": stage, "profile": profile, "timeout": timeout, "cwd": cwd})
        if write:
            write(cmd, cwd)
        return SimpleNamespace(returncode=returncode, stdout=o, stderr=e, timed_out=timed_out)

    run.calls = calls
    return run


def install_writer(cmd, cwd):
    marker = Path(cwd) / "node_modules" / "knip" / "bin" / "knip.js"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("//")


def tools():
    return {t["id"]: t for t in toolcheck.load_tools()["tools"]}


class TestLockfile:
    @pytest.mark.parametrize("tool_id", sorted(PACKAGES))
    def test_lock_version_matches_the_tools_json_pin(self, tool_id):
        lock = json.loads((LOCK_DIR / "package-lock.json").read_text())

        assert lock["packages"]["node_modules/" + PACKAGES[tool_id]]["version"] == tools()[tool_id]["version"]

    def test_package_json_pins_exact_versions(self):
        pkg = json.loads((LOCK_DIR / "package.json").read_text())

        assert pkg["dependencies"] == {PACKAGES[k]: tools()[k]["version"] for k in PACKAGES}

    def test_typescript_is_installed_once_at_the_top_level(self):
        lock = json.loads((LOCK_DIR / "package-lock.json").read_text())

        copies = [k for k in lock["packages"] if k == "node_modules/typescript" or k.endswith("/node_modules/typescript")]
        assert copies == ["node_modules/typescript"]

    def test_tools_json_names_the_lock_folder_for_every_package(self):
        for tool_id in PACKAGES:
            assert tools()[tool_id]["node_lock"] == "node/js-tools"

    def test_node_minimum_for_js_is_22_13(self):
        node = next(h for h in toolcheck.load_tools()["host"] if h["id"] == "node")

        assert node["min"]["js"] == "22.13.0"

    def test_tools_name_the_cards_they_feed(self):
        t = tools()

        assert t["knip"]["cards"] == ["change.dead-code"]
        assert t["dependency-cruiser"]["cards"] == tools()["grimp"]["cards"]
        assert t["scip-typescript"]["cards"] == tools()["scip-python"]["cards"]
        assert t["typescript"]["cards"] == ["data.entities", "data.relationships", "entry.catalog", "interactions.graph"]
        assert "open" not in t["typescript"]


class TestInstallDir:
    def test_folder_is_named_by_the_first_eight_hex_of_the_lock_sha(self, tmp_path):
        assert js_tools.install_dir(tmp_path, "0123456789abcdef") == tmp_path / ".dossier-tools/node/js-tools-01234567"


class TestEnsureInstalled:
    def test_runs_npm_ci_once_with_scripts_off(self, tmp_path):
        run = fake_run(tmp_path, write=install_writer)

        folder = js_tools.ensure_installed(run, tmp_path, 60)

        call = run.calls[0]
        assert call["cmd"] == ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"]
        assert (call["profile"], call["timeout"], call["cwd"]) == ("tool", 60, folder)
        for name in ("package.json", "package-lock.json", "ts_facts.mjs"):
            assert (folder / name).exists()

    def test_folder_name_comes_from_the_lockfile(self, tmp_path):
        run = fake_run(tmp_path, write=install_writer)
        sha = hashlib.sha1((LOCK_DIR / "package-lock.json").read_bytes()).hexdigest()

        assert js_tools.ensure_installed(run, tmp_path, 60) == js_tools.install_dir(tmp_path, sha)

    def test_second_call_with_a_matching_marker_does_not_run_again(self, tmp_path):
        run = fake_run(tmp_path, write=install_writer)
        js_tools.ensure_installed(run, tmp_path, 60)

        js_tools.ensure_installed(run, tmp_path, 60)

        assert len(run.calls) == 1

    def test_changed_ts_facts_installs_again(self, tmp_path, monkeypatch):
        run = fake_run(tmp_path, write=install_writer)
        js_tools.ensure_installed(run, tmp_path, 60)
        other = tmp_path / "elsewhere"
        other.mkdir()
        for name in ("package.json", "package-lock.json"):
            (other / name).write_bytes((LOCK_DIR / name).read_bytes())
        (other / "ts_facts.mjs").write_text("// changed\n")
        monkeypatch.setattr(js_tools, "NODE_DIR", other)

        js_tools.ensure_installed(run, tmp_path, 60)

        assert len(run.calls) == 2

    def test_failed_install_raises_with_the_stderr_tail(self, tmp_path):
        with pytest.raises(shared_tools.ToolError, match="last line"):
            js_tools.ensure_installed(fake_run(tmp_path, returncode=1), tmp_path, 60)

    def test_timeout_raises(self, tmp_path):
        with pytest.raises(shared_tools.ToolError, match="took too long"):
            js_tools.ensure_installed(fake_run(tmp_path, timed_out=True, returncode=None), tmp_path, 1)

    def test_missing_program_file_after_install_raises(self, tmp_path):
        with pytest.raises(shared_tools.ToolError, match="missing"):
            js_tools.ensure_installed(fake_run(tmp_path), tmp_path, 60)


class TestNodeProblem:
    def test_not_installed(self, tmp_path):
        assert js_tools.node_problem(fake_run(tmp_path, returncode=127)) == "Node is not installed."

    def test_too_old(self, tmp_path):
        got = js_tools.node_problem(fake_run(tmp_path, out="v20.19.2\n"))

        assert got == "Node 20.19.2 is too old; these tools need 22.13.0 or later."

    def test_new_enough(self, tmp_path):
        run = fake_run(tmp_path, out="v26.13.0\n")

        assert js_tools.node_problem(run) is None
        assert (run.calls[0]["cmd"], run.calls[0]["profile"], run.calls[0]["timeout"]) == (["node", "--version"], "tool", 15)

    def test_unreadable_version_counts_as_not_installed(self, tmp_path):
        assert js_tools.node_problem(fake_run(tmp_path, out="what\n")) == "Node is not installed."


class TestKnipClient:
    def _run(self, tmp_path, code, out="", err=""):
        def run(cmd, *, cwd, stage, profile, timeout):
            (tmp_path / "o").write_text(out)
            (tmp_path / "e").write_text(err)
            return SimpleNamespace(returncode=code, timed_out=False, stdout=tmp_path / "o", stderr=tmp_path / "e")
        return run

    def test_exit_two_raises_with_the_first_stderr_line(self, tmp_path):
        knip = js_tools.Knip(self._run(tmp_path, 2, err="\nCould not load config\nmore\n"), Path("/x"), 60)

        with pytest.raises(shared_tools.ToolError, match=r"knip failed \(exit 2\): Could not load config"):
            knip.run_knip(Path("/r"))

    def test_json_on_stdout_is_returned(self, tmp_path):
        knip = js_tools.Knip(self._run(tmp_path, 0, out='{"issues": []}'), Path("/x"), 60)

        assert knip.run_knip(Path("/r")) == {"issues": []}

    def test_output_that_is_not_json_raises(self, tmp_path):
        knip = js_tools.Knip(self._run(tmp_path, 0, out="oops"), Path("/x"), 60)

        with pytest.raises(shared_tools.ToolError, match="not JSON"):
            knip.run_knip(Path("/r"))
