"""The safe runner for restores and tools: empty environment plus an allowlist, scratch HOME, private caches,
and a process-group timeout. This is hygiene, not isolation: the child still runs with the user's rights.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import config
import toolcheck

PASS_THROUGH = ("LANG", "LC_ALL", "TERM")
NETWORK = ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "NODE_EXTRA_CA_CERTS")
ALLOWED_NAMES = frozenset({
    "PATH", *PASS_THROUGH, "HOME", "TMPDIR", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", *NETWORK,
    "DOTNET_CLI_TELEMETRY_OPTOUT", "DOTNET_NOLOGO", "UV_CACHE_DIR", "npm_config_cache", "NUGET_PACKAGES",
    "DOTNET_CLI_HOME", "PIP_CACHE_DIR", "npm_config_userconfig", "UV_PYTHON_INSTALL_DIR",
    "GH_CONFIG_DIR", "GH_PROMPT_DISABLED", "GH_NO_UPDATE_NOTIFIER",
    "YARN_CACHE_FOLDER", "YARN_GLOBAL_FOLDER", "YARN_ENABLE_TELEMETRY",
})
SAFE_PATH = ("/usr/local/bin", "/usr/bin", "/bin")


@dataclass
class Result:
    command: list[str]
    returncode: int | None
    timed_out: bool
    seconds: float
    stdout: Path
    stderr: Path
    env_names: list[str]


def tools_cache(area: Path) -> Path:
    return Path(area).parent / ".dossier-tools"


def _host_path(parent: Mapping[str, str]) -> str:
    dirs: list[str] = []
    for t in toolcheck.load_tools()["host"]:
        exe = shutil.which(t["command"][0], path=parent.get("PATH", ""))
        d = str(Path(exe).parent) if exe else None
        if d and d not in dirs:
            dirs.append(d)
    # git lives in /usr/bin and comes first, so a newer node from a version manager must be moved ahead of the system folders
    dirs = [d for d in dirs if d not in SAFE_PATH] + [d for d in dirs if d in SAFE_PATH]
    for d in SAFE_PATH:
        if d not in dirs:
            dirs.append(d)
    return os.pathsep.join(dirs)


def _registry(area: Path, ecosystem: str, parent: Mapping[str, str], env: dict[str, str]) -> None:
    real_home = Path.home().resolve()
    for entry in config.registry_auth().get(ecosystem, []):
        if entry.startswith("~/"):
            src = (Path.home() / entry[2:]).resolve()
            try:
                rel = src.relative_to(real_home)
            except ValueError:
                raise SystemExit(f"registry_auth.{ecosystem}: {entry} is outside your home folder, so it was not copied.")
            if src.is_file():
                dest = Path(area) / "home" / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dest)
                dest.chmod(0o600)
                if rel.name == ".npmrc":
                    env["npm_config_userconfig"] = str(dest)
        elif entry in parent:
            env[entry] = parent[entry]


def build_env(area: Path, *, profile: str = "restricted", ecosystem: str | None = None,
              parent: Mapping[str, str] | None = None) -> dict[str, str]:
    area = Path(area)
    parent = os.environ if parent is None else parent
    home = area / "home"
    env: dict[str, str] = {"PATH": _host_path(parent)}
    for k in (*PASS_THROUGH, *NETWORK):
        if k in parent:
            env[k] = parent[k]
    env.update(HOME=str(home), TMPDIR=str(home / "tmp"), XDG_CACHE_HOME=str(home / ".cache"),
               XDG_CONFIG_HOME=str(home / ".config"), DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1")
    cache = area / "cache"
    env.update(npm_config_cache=str(cache / "npm"), NUGET_PACKAGES=str(cache / "nuget"),
               DOTNET_CLI_HOME=str(cache / "dotnet"), PIP_CACHE_DIR=str(cache / "pip"),
               npm_config_userconfig=str(home / ".npmrc-empty"), YARN_CACHE_FOLDER=str(cache / "yarn"),
               YARN_GLOBAL_FOLDER=str(cache / "yarn-berry"), YARN_ENABLE_TELEMETRY="0")
    if profile == "tool":
        shared = tools_cache(area)
        env.update(UV_CACHE_DIR=str(shared / "uv"), UV_PYTHON_INSTALL_DIR=str(shared / "python"),
                   npm_config_cache=str(shared / "npm"))
    else:
        env["UV_CACHE_DIR"] = str(cache / "uv")
    if profile == "github":     # `gh` finds its login in its own config folder; no token variable is ever passed
        env.update(GH_CONFIG_DIR=parent.get("GH_CONFIG_DIR") or str(Path(parent.get("XDG_CONFIG_HOME") or Path(parent.get("HOME") or Path.home()) / ".config") / "gh"),
                   GH_PROMPT_DISABLED="1", GH_NO_UPDATE_NOTIFIER="1")
    for d in (home / "tmp", home / ".cache", home / ".config"):
        d.mkdir(parents=True, exist_ok=True)
    (home / ".npmrc-empty").touch()
    if ecosystem and profile == "restricted":
        _registry(area, ecosystem, parent, env)
    return env


def _kill_group(pid: int, sig: int) -> None:
    try:
        os.killpg(pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def run(cmd: list[str], *, area: Path, cwd: Path, stage: str, timeout: float, profile: str = "restricted",
        ecosystem: str | None = None, input: bytes | None = None, parent: Mapping[str, str] | None = None) -> Result:
    area = Path(area)
    env = build_env(area, profile=profile, ecosystem=ecosystem, parent=parent)
    logs = area / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    n = 1
    while (logs / f"{stage}-{n}.out").exists():
        n += 1
    out_p, err_p = logs / f"{stage}-{n}.out", logs / f"{stage}-{n}.err"
    stdin = subprocess.DEVNULL
    if input is not None:
        in_p = logs / f"{stage}-{n}.in"
        in_p.write_bytes(input)
        stdin = open(in_p, "rb")
    t0 = time.monotonic()
    timed_out = False
    with open(out_p, "wb") as fo, open(err_p, "wb") as fe:
        try:
            p = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=stdin, stdout=fo, stderr=fe, start_new_session=True)
        except OSError as e:
            fe.write(f"Could not start {cmd[0]}: {e}\n".encode())
            return Result(list(cmd), 127, False, 0.0, out_p, err_p, sorted(env))
        finally:
            if input is not None:
                stdin.close()
        try:
            p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_group(p.pid, signal.SIGTERM)
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            _kill_group(p.pid, signal.SIGKILL)
            p.wait()
        else:
            _kill_group(p.pid, signal.SIGKILL)
    return Result(list(cmd), None if timed_out else p.returncode, timed_out, round(time.monotonic() - t0, 2),
                  out_p, err_p, sorted(env))
