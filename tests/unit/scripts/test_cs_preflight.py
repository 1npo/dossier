import os
import shlex
import shutil
import subprocess

import toolcheck

GLOBAL = '{"sdk": {"version": "10.0.403", "rollForward": "latestFeature"}}'


def make_repo(tmp_path, files):
    r = tmp_path / "repo"
    r.mkdir()
    for name, text in files.items():
        (r / name).parent.mkdir(parents=True, exist_ok=True)
        (r / name).write_text(text)
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
    for args in (["init", "-b", "main"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@x", "commit", "-m", "m"]):
        subprocess.run(["git", "-C", str(r), *args], check=True, capture_output=True, env=env)
    sha = subprocess.run(["git", "-C", str(r), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    return str(r), sha


def fake_bin(tmp_path, **tools):
    d = tmp_path / "bin"
    d.mkdir()
    (d / "git").symlink_to(shutil.which("git"))
    for name, out in tools.items():
        f = d / name
        f.write_text("#!/bin/sh\nprintf '%s\\n' " + shlex.quote(out) + "\n")
        f.chmod(0o755)
    return str(d)


class TestPreflightAt:
    def test_old_sdk_for_the_global_json_is_marked_too_old(self, tmp_path):
        top, sha = make_repo(tmp_path, {"global.json": GLOBAL, "a.cs": "class A {}\n"})
        path = fake_bin(tmp_path, dotnet="10.0.114 [/x]", uv="uv 0.11.19")

        report = toolcheck.preflight_at(top, sha, path=path)

        host = next(h for h in report["host"] if h["id"] == "dotnet")
        assert host["status"] == "old" and host["needs"] == "10.0.403 (latestFeature) for global.json"
        assert "dotnet" in report["missing"]
        assert "TOO OLD  dotnet" in toolcheck.format_text(report)

    def test_matching_sdk_leaves_the_report_alone(self, tmp_path):
        top, sha = make_repo(tmp_path, {"global.json": GLOBAL, "a.cs": "class A {}\n"})
        path = fake_bin(tmp_path, dotnet="10.0.403 [/x]", uv="uv 0.11.19")

        report = toolcheck.preflight_at(top, sha, path=path)

        assert next(h for h in report["host"] if h["id"] == "dotnet")["status"] == "ok"

    def test_python_only_tree_gives_exactly_todays_report(self, tmp_path):
        top, sha = make_repo(tmp_path, {"a.py": "print(1)\n", "global.json": GLOBAL})
        path = fake_bin(tmp_path, dotnet="10.0.114 [/x]", uv="uv 0.11.19", node="v22.14.0", npm="9.2.0")

        report = toolcheck.preflight_at(top, sha, path=path)

        assert report == toolcheck.preflight(toolcheck.languages_at(top, sha), path=path)
