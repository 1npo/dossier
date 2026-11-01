import os
import subprocess
import time

import pytest

import sandbox
import workarea


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("DOSSIER_CONFIG", str(tmp_path / "cfg.json"))


@pytest.fixture
def area(tmp_path):
    a = tmp_path / "cache" / "repo"
    a.mkdir(parents=True)
    return a


def run(area, cmd, **kw):
    return sandbox.run(cmd, area=area, cwd=area, stage=kw.pop("stage", "t"), timeout=kw.pop("timeout", 20), **kw)


def gone(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


class TestRun:
    def test_child_sees_exactly_the_recorded_names(self, area):
        r = run(area, ["sh", "-c", "env | cut -d= -f1 | sort"], parent={"PATH": "/usr/bin:/bin", "SECRET_X": "1"})

        names = r.stdout.read_text().split()
        assert set(names) - {"PWD", "SHLVL", "_", "OLDPWD"} == set(r.env_names)
        assert "SECRET_X" not in names

    def test_stdout_and_stderr_go_to_separate_files(self, area):
        r = run(area, ["sh", "-c", "echo out; echo err >&2"])

        assert (r.stdout.read_text(), r.stderr.read_text()) == ("out\n", "err\n")

    def test_input_reaches_stdin(self, area):
        r = run(area, ["sh", "-c", "cat"], input=b'{"a":1}')

        assert r.stdout.read_text() == '{"a":1}'

    def test_timeout_kills_the_whole_process_group(self, area, hygiene_repo):
        co = workarea.ensure_checkout(workarea.area_for("h", hygiene_repo.path, "r", area.parent), hygiene_repo.path, hygiene_repo.main_sha)
        t0 = time.monotonic()

        r = sandbox.run(["sh", "sleeper.sh"], area=area, cwd=co["path"], stage="sleep", timeout=1)

        assert r.timed_out and r.returncode is None
        home = area / "home"
        pids = [int((home / n).read_text()) for n in ("child.pid", "parent.pid")]
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not all(gone(p) for p in pids):
            time.sleep(0.1)
        assert all(gone(p) for p in pids) and time.monotonic() - t0 < 10

    def test_background_child_does_not_outlive_a_normal_exit(self, area):
        r = run(area, ["sh", "-c", 'sleep 300 & echo $! > "$HOME/bg.pid"'])

        pid = int((area / "home" / "bg.pid").read_text())
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not gone(pid):
            time.sleep(0.1)
        assert r.returncode == 0 and gone(pid)

    def test_missing_program_reports_127_with_a_message(self, area):
        r = run(area, ["definitely-not-a-program"])

        assert r.returncode == 127 and "Could not start" in r.stderr.read_text()
