"""Which .NET SDK a repository asks for (global.json) and whether this machine has one (plan 011, D6).

The roll-forward rules follow https://learn.microsoft.com/dotnet/core/tools/global-json. Dossier never forces a roll-forward:
it does not edit global.json, set DOTNET_ROLL_FORWARD or pass an SDK version.
"""
import json
import re
import shutil
import subprocess

import gather

DEFAULT_RULE = "patch"


def _strip_comments(text: str) -> str:
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def parse_global_json(text: str) -> dict | None:
    try:
        data = json.loads(_strip_comments(text.lstrip("﻿")))
    except (ValueError, TypeError):
        return None
    sdk = data.get("sdk") if isinstance(data, dict) else None
    return sdk if isinstance(sdk, dict) else None


def _key(version: str) -> tuple | None:
    """(major, minor, feature band, patch) for x.y.znn, or None."""
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", version or "")
    if not m:
        return None
    major, minor, third = (int(g) for g in m.groups())
    return major, minor, third // 100, third % 100


def pick(installed: list[str], want: dict | None) -> str | None:
    pre = bool(want and want.get("allowPrerelease"))
    have = [(k, v) for v in installed if (k := _key(v)) and (pre or "-" not in v)]
    if not want or not want.get("version") or _key(want["version"]) is None:
        return max(have)[1] if have else None
    req, rule = _key(want["version"]), want.get("rollForward") or DEFAULT_RULE
    same_band = [(k, v) for k, v in have if k[:3] == req[:3] and k[3] >= req[3]]
    if rule == "disable":
        return next((v for k, v in have if k == req), None)
    if rule in ("patch", "latestPatch"):
        return max(same_band)[1] if same_band else None
    if rule in ("latestFeature", "latestMinor", "latestMajor"):
        width = {"latestFeature": 2, "latestMinor": 1, "latestMajor": 0}[rule]
        found = [(k, v) for k, v in have if k[:width] == req[:width] and k >= req]
        return max(found)[1] if found else None
    if rule in ("feature", "minor", "major"):
        if same_band:
            return max(same_band)[1]
        width = {"feature": 2, "minor": 1, "major": 0}[rule]
        higher = [(k, v) for k, v in have if k[:width] == req[:width] and k[:3] > req[:3]]
        if not higher:
            return None
        lowest = min(k[:3] for k, _ in higher)
        return max((k, v) for k, v in higher if k[:3] == lowest)[1]
    return None


def requirements(paths, read) -> list[dict]:
    out = []
    for p in sorted(paths):
        if p.rsplit("/", 1)[-1] != "global.json" or gather.noise_reason(p):
            continue
        sdk = parse_global_json(read(p) or "")
        if sdk and sdk.get("version"):
            out.append({"path": p, "version": sdk["version"], "rollForward": sdk.get("rollForward") or DEFAULT_RULE,
                        **({"allowPrerelease": True} if sdk.get("allowPrerelease") else {})})
    return out


def _unmet(installed: list[str], reqs: list[dict]) -> dict | None:
    return next((r for r in reqs if pick(installed, r) is None), None)


def problem(installed: list[str], reqs: list[dict]) -> str | None:
    if not installed:
        return "The .NET SDK is not installed."
    bad = _unmet(installed, reqs)
    if bad:
        return (f"The repository asks for .NET SDK {bad['version']} ({bad['rollForward']}) in {bad['path']}, "
                f"and this machine has {', '.join(installed) or 'none'}.")
    return None


def apply(report: dict, reqs: list[dict], installed: list[str]) -> None:
    """Preflight: mark the dotnet host entry too old when a global.json asks for an SDK this machine cannot give."""
    host = next((h for h in report["host"] if h["id"] == "dotnet"), None)
    if not host or host["status"] != "ok":
        return
    bad = _unmet(installed, reqs)
    if bad:
        host["status"] = "old"
        host["needs"] = f"{bad['version']} ({bad['rollForward']}) for {bad['path']}"
        report["missing"] = sorted(set(report["missing"]) | {"dotnet"})


def runtime_majors(text: str) -> list[int]:
    return sorted({int(m.group(1)) for m in re.finditer(r"(?m)^Microsoft\.NETCore\.App (\d+)\.", text)})


def _dotnet(args: list[str], path: str | None) -> str:
    exe = shutil.which("dotnet", path=path)
    if not exe:
        return ""
    try:
        return subprocess.run([exe, *args], capture_output=True, text=True, timeout=15, env=None if path is None else {"PATH": path}).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def list_sdks(path: str | None = None) -> list[str]:
    return re.findall(r"(?m)^(\d+\.\d+\.\d+\S*)\s", _dotnet(["--list-sdks"], path))


def list_runtime_majors(path: str | None = None) -> list[int]:
    return runtime_majors(_dotnet(["--list-runtimes"], path))
