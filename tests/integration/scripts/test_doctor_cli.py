import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dossier.py"


def fake(bin_dir, name, out):
    f = bin_dir / name
    f.write_text("#!/bin/sh\nprintf '%s\\n' " + shlex.quote(out) + "\n")
    f.chmod(0o755)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    (r / "a.py").write_text("print(1)\n")
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
    for args in (["init", "-b", "main"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@x", "commit", "-m", "m"]):
        subprocess.run(["git", "-C", str(r), *args], check=True, capture_output=True, env=env)
    return r


@pytest.fixture
def bin_dir(tmp_path):
    d = tmp_path / "bin"
    d.mkdir()
    (d / "git").symlink_to(shutil.which("git"))
    fake(d, "uv", "uv 0.11.19")
    return d


def doctor(repo, bin_dir):
    env = {"PATH": str(bin_dir), "DOSSIER_CONFIG": str(bin_dir / "none.json")}
    return subprocess.run([sys.executable, str(SCRIPT), "doctor", str(repo), "--json"], capture_output=True, text=True, env=env)


class TestDoctorCli:
    def test_missing_node_and_npm_exit_1(self, repo, bin_dir):
        r = doctor(repo, bin_dir)

        assert r.returncode == 1
        assert {"node", "npm"} <= set(json.loads(r.stdout)["missing"])

    def test_everything_present_exits_0(self, repo, bin_dir):
        fake(bin_dir, "node", "v20.19.2")
        fake(bin_dir, "npm", "9.2.0")

        r = doctor(repo, bin_dir)

        assert r.returncode == 0, r.stdout
        assert json.loads(r.stdout)["missing"] == []


class TestDoctorCliDotnetSdk:
    def cs_repo(self, tmp_path):
        r = tmp_path / "csrepo"
        r.mkdir()
        (r / "global.json").write_text('{"sdk": {"version": "10.0.403", "rollForward": "latestFeature"}}')
        (r / "A.cs").write_text("class A {}\n")
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
        for args in (["init", "-b", "main"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@x", "commit", "-m", "m"]):
            subprocess.run(["git", "-C", str(r), *args], check=True, capture_output=True, env=env)
        return r

    def test_old_sdk_for_the_global_json_prints_too_old_and_exits_1(self, tmp_path, bin_dir):
        fake(bin_dir, "dotnet", "10.0.114 [/x]")
        env = {"PATH": str(bin_dir), "DOSSIER_CONFIG": str(bin_dir / "none.json")}

        r = subprocess.run([sys.executable, str(SCRIPT), "doctor", str(self.cs_repo(tmp_path))], capture_output=True, text=True, env=env)

        assert r.returncode == 1
        assert "TOO OLD  dotnet 10.0.114" in r.stdout
