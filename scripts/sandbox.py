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

from dossier.core import config
import toolcheck

PASS_THROUGH = ("LANG", "LC_ALL", "TERM")
NETWORK = ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "NODE_EXTRA_CA_CERTS")
ALLOWED_NAMES = frozenset({
    "PATH", *PASS_THROUGH, "HOME", "TMPDIR", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", *NETWORK,
    "DOTNET_CLI_TELEMETRY_OPTOUT", "DOTNET_NOLOGO", "UV_CACHE_DIR", "npm_config_cache", "NUGET_PACKAGES",
    "DOTNET_CLI_HOME", "DOTNET_ROOT", "MSBUILDDISABLENODEREUSE", "DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE",
    "DOTNET_GENERATE_ASPNET_CERTIFICATE", "DOTNET_ADD_GLOBAL_TOOLS_TO_PATH", "DOTNET_SKIP_FIRST_TIME_EXPERIENCE", "PIP_CACHE_DIR", "npm_config_userconfig", "UV_PYTHON_INSTALL_DIR",
    "GH_CONFIG_DIR", "GH_PROMPT_DISABLED", "GH_NO_UPDATE_NOTIFIER",
    "YARN_CACHE_FOLDER", "YARN_GLOBAL_FOLDER", "YARN_ENABLE_TELEMETRY",
    "SYSTEMROOT", "SystemDrive", "WINDIR", "COMSPEC", "PATHEXT", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "OS",
    "USERPROFILE", "TEMP", "TMP", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH",
})
SAFE_PATH = ("/usr/local/bin", "/usr/bin", "/bin")
# Windows needs these from the parent or most programs (uv, git, python) cannot start or fall back to C:\Windows.
WINDOWS_PASS_THROUGH = ("SYSTEMROOT", "SystemDrive", "WINDIR", "COMSPEC", "PATHEXT", "NUMBER_OF_PROCESSORS",
                        "PROCESSOR_ARCHITECTURE", "OS")
WINDOWS = os.name == "nt"   # a module flag, so tests can exercise the Windows branches on any system


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


def _parent_get(parent: Mapping[str, str], name: str) -> str | None:
    """Windows environment names are case-insensitive, and os.environ upper-cases them."""
    if name in parent:
        return parent[name]
    if WINDOWS:
        for k, v in parent.items():
            if k.upper() == name.upper():
                return v
    return None


def _safe_path(parent: Mapping[str, str]) -> tuple[str, ...]:
    if WINDOWS:
        root = _parent_get(parent, "SYSTEMROOT") or _parent_get(parent, "WINDIR") or r"C:\Windows"
        return (os.path.join(root, "System32"), root)
    return SAFE_PATH


def _host_path(parent: Mapping[str, str]) -> str:
    dirs: list[str] = []
    for t in toolcheck.load_tools()["host"]:
        exe = shutil.which(t["command"][0], path=parent.get("PATH", ""))
        d = str(Path(exe).parent) if exe else None
        if d and d not in dirs:
            dirs.append(d)
    # git lives in /usr/bin and comes first, so a newer node from a version manager must be moved ahead of the system folders
    safe = _safe_path(parent)
    dirs = [d for d in dirs if d not in safe] + [d for d in dirs if d in safe]
    for d in safe:
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
    for k in (*PASS_THROUGH, *NETWORK, "DOTNET_ROOT"):
        if k in parent:
            env[k] = parent[k]
    env.update(HOME=str(home), TMPDIR=str(home / "tmp"), XDG_CACHE_HOME=str(home / ".cache"),
               XDG_CONFIG_HOME=str(home / ".config"), DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1",
               MSBUILDDISABLENODEREUSE="1", DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE="1", DOTNET_GENERATE_ASPNET_CERTIFICATE="false",
               DOTNET_ADD_GLOBAL_TOOLS_TO_PATH="false", DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1")
    if WINDOWS:
        for k in WINDOWS_PASS_THROUGH:
            v = _parent_get(parent, k)
            if v is not None:
                env[k] = v
        # Point every per-user location at the scratch home so nothing falls back to C:\Windows or the real profile.
        env.update(USERPROFILE=str(home), TEMP=str(home / "tmp"), TMP=str(home / "tmp"),
                   APPDATA=str(home / "AppData" / "Roaming"), LOCALAPPDATA=str(home / "AppData" / "Local"),
                   HOMEDRIVE=home.drive, HOMEPATH=str(home)[len(home.drive):])
        for d in (home / "AppData" / "Roaming", home / "AppData" / "Local"):
            d.mkdir(parents=True, exist_ok=True)
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


def _kill_group(pid: int, sig: int | None = None) -> None:
    if WINDOWS:
        # Windows has no process groups or SIGKILL: kill the whole process tree.
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=10)
        except (OSError, subprocess.SubprocessError):
            pass
        return
    try:
        os.killpg(pid, sig if sig is not None else signal.SIGKILL)
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
            p = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=stdin, stdout=fo, stderr=fe, start_new_session=not WINDOWS)
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
            _kill_group(p.pid, getattr(signal, "SIGTERM", None))
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            _kill_group(p.pid)
            p.wait()
        else:
            _kill_group(p.pid)
    return Result(list(cmd), None if timed_out else p.returncode, timed_out, round(time.monotonic() - t0, 2),
                  out_p, err_p, sorted(env))
