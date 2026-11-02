import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import scip_tool
import shared_tools
import toolcheck

SCRIPTS = Path(shared_tools.__file__).parent


def fake_run(tmp_path, returncode=0, timed_out=False, write=None):
    calls = []

    def run(cmd, *, stage, profile, timeout, cwd=None):
        out, err = tmp_path / "o", tmp_path / "e"
        out.write_text("")
        err.write_text("boom\nlast line")
        calls.append({"cmd": cmd, "stage": stage, "profile": profile, "timeout": timeout, "cwd": cwd})
        if write:
            write(cmd, cwd)
        return SimpleNamespace(returncode=returncode, stdout=out, stderr=err, timed_out=timed_out)

    run.calls = calls
    return run


def install_writer(cmd, cwd):
    index = Path(cwd) / scip_tool.INDEX_JS
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text("//")


class TestLockfile:
    def test_lock_version_matches_the_tools_json_pin(self):
        lock = json.loads((SCRIPTS / "node/scip-python/package-lock.json").read_text())
        pinned = next(t["version"] for t in toolcheck.load_tools()["tools"] if t["id"] == "scip-python")

        assert lock["packages"]["node_modules/@sourcegraph/scip-python"]["version"] == pinned

    def test_package_json_pins_the_same_version(self):
        pkg = json.loads((SCRIPTS / "node/scip-python/package.json").read_text())
        pinned = next(t["version"] for t in toolcheck.load_tools()["tools"] if t["id"] == "scip-python")

        assert pkg["dependencies"] == {"@sourcegraph/scip-python": pinned}

    def test_tools_json_names_the_lock_folder(self):
        entry = next(t for t in toolcheck.load_tools()["tools"] if t["id"] == "scip-python")

        assert entry["node_lock"] == "node/scip-python" and (SCRIPTS / entry["node_lock"] / "package-lock.json").exists()


class TestInstallDir:
    def test_folder_is_under_the_shared_tool_cache(self, tmp_path):
        assert scip_tool.install_dir(tmp_path, "0.6.6") == tmp_path / ".dossier-tools/node/scip-python-0.6.6"


class TestEnsureInstalled:
    def test_runs_npm_ci_once_with_scripts_off_in_the_install_folder(self, tmp_path):
        run = fake_run(tmp_path, write=install_writer)

        index = scip_tool.ensure_installed(run, tmp_path, "0.6.6", 60)

        call = run.calls[0]
        assert call["cmd"] == ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"]
        assert (call["profile"], call["timeout"], call["cwd"]) == ("tool", 60, scip_tool.install_dir(tmp_path, "0.6.6"))
        assert index == scip_tool.install_dir(tmp_path, "0.6.6") / scip_tool.INDEX_JS

    def test_second_call_with_a_matching_marker_does_not_run_again(self, tmp_path):
        run = fake_run(tmp_path, write=install_writer)
        scip_tool.ensure_installed(run, tmp_path, "0.6.6", 60)

        scip_tool.ensure_installed(run, tmp_path, "0.6.6", 60)

        assert len(run.calls) == 1

    def test_changed_lock_marker_installs_again(self, tmp_path):
        run = fake_run(tmp_path, write=install_writer)
        scip_tool.ensure_installed(run, tmp_path, "0.6.6", 60)
        (scip_tool.install_dir(tmp_path, "0.6.6") / ".installed").write_text("old\n")

        scip_tool.ensure_installed(run, tmp_path, "0.6.6", 60)

        assert len(run.calls) == 2

    def test_failed_install_raises_with_the_stderr_tail(self, tmp_path):
        run = fake_run(tmp_path, returncode=1)

        with pytest.raises(shared_tools.ToolError, match="last line"):
            scip_tool.ensure_installed(run, tmp_path, "0.6.6", 60)

    def test_timeout_raises(self, tmp_path):
        with pytest.raises(shared_tools.ToolError, match="took too long"):
            scip_tool.ensure_installed(fake_run(tmp_path, timed_out=True, returncode=None), tmp_path, "0.6.6", 1)

    def test_missing_program_file_after_install_raises(self, tmp_path):
        with pytest.raises(shared_tools.ToolError, match="missing"):
            scip_tool.ensure_installed(fake_run(tmp_path), tmp_path, "0.6.6", 60)


class TestEnvironment:
    def test_installed_packages_come_from_dist_info_folders(self, tmp_path):
        dist = tmp_path / ".venv/lib/python3.13/site-packages/requests-2.32.0.dist-info"
        dist.mkdir(parents=True)
        (dist / "METADATA").write_text("Metadata-Version: 2.1\nName: requests\nVersion: 2.32.0\n")
        (dist / "RECORD").write_text("requests/__init__.py,sha256=x,10\nrequests-2.32.0.dist-info/METADATA,sha256=y,5\n")

        got = scip_tool.environment(tmp_path)

        assert got == [{"name": "requests", "version": "2.32.0",
                        "files": ["requests/__init__.py", "requests-2.32.0.dist-info/METADATA"]}]

    def test_no_venv_gives_empty(self, tmp_path):
        assert scip_tool.environment(tmp_path) == []

    def test_dist_info_without_metadata_is_skipped(self, tmp_path):
        (tmp_path / ".venv/lib/python3.13/site-packages/x-1.dist-info").mkdir(parents=True)

        assert scip_tool.environment(tmp_path) == []


class TestRunIndex:
    def writer(self, size=5):
        def write(cmd, cwd):
            Path(cmd[cmd.index("--output") + 1]).write_bytes(b"x" * size)
        return write

    def test_output_is_inside_the_area_and_the_profile_is_restricted(self, tmp_path):
        area, checkout = tmp_path / "area", tmp_path / "co"
        checkout.mkdir()
        run = fake_run(tmp_path, write=self.writer())

        got = scip_tool.run_index(run, "/tool/index.js", checkout, area, "shopcart", "abc123", 90)

        cmd = run.calls[0]["cmd"]
        assert got == area / "scip" / "index.scip" and cmd[cmd.index("--output") + 1] == str(got)
        assert (run.calls[0]["profile"], run.calls[0]["timeout"], run.calls[0]["stage"]) == ("restricted", 90, "scip-python")

    def test_project_name_version_and_environment_file_are_passed(self, tmp_path):
        area, checkout = tmp_path / "area", tmp_path / "co"
        checkout.mkdir()
        run = fake_run(tmp_path, write=self.writer())

        scip_tool.run_index(run, "/tool/index.js", checkout, area, "shopcart", "abc123", 90)

        cmd = run.calls[0]["cmd"]
        assert cmd[:4] == ["node", "/tool/index.js", "index", "."]
        assert cmd[cmd.index("--project-name") + 1] == "shopcart" and cmd[cmd.index("--project-version") + 1] == "abc123"
        assert json.loads((area / "scip" / "env.json").read_text()) == []

    def test_nonzero_exit_raises_even_when_a_file_was_written(self, tmp_path):
        run = fake_run(tmp_path, returncode=1, write=self.writer())

        with pytest.raises(shared_tools.ToolError, match="last line"):
            scip_tool.run_index(run, "/i.js", tmp_path, tmp_path / "area", "r", "s", 1)

    def test_empty_index_raises(self, tmp_path):
        run = fake_run(tmp_path, write=self.writer(size=0))

        with pytest.raises(shared_tools.ToolError, match="without writing"):
            scip_tool.run_index(run, "/i.js", tmp_path, tmp_path / "area", "r", "s", 1)

    def test_stale_index_from_an_earlier_run_is_removed_first(self, tmp_path):
        area = tmp_path / "area"
        (area / "scip").mkdir(parents=True)
        (area / "scip" / "index.scip").write_bytes(b"old")

        with pytest.raises(shared_tools.ToolError, match="without writing"):
            scip_tool.run_index(fake_run(tmp_path), "/i.js", tmp_path, area, "r", "s", 1)
