"""Which tools a repository needs, and which of them this machine has. Reads tools.json. Installs nothing."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import cs_sdk
import gather

TOOLS_FILE = Path(__file__).resolve().parent / "tools.json"
HOST_FOR_VIA = {"uv": ["uv"], "npx": ["node", "npm"], "dotnet-tool": ["dotnet"], "sdk": ["dotnet"], "repo-config": []}


def load_tools(path=TOOLS_FILE) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def scope_of(lang: str, tools: dict) -> str | None:
    return tools["languages"].get(lang)


def tier_of(lang: str, tools: dict) -> str:
    return "A" if scope_of(lang, tools) else "B"


def languages_at(top: str, sha: str) -> list[str]:
    """Code languages among the tracked files at sha, by name and extension only (no file contents are read)."""
    r = subprocess.run(["git", "-C", top, "ls-tree", "-r", "--name-only", "-z", sha], capture_output=True)
    count: Counter = Counter()
    for p in r.stdout.decode("utf-8", "replace").split("\0"):
        if not p or gather.noise_reason(p):
            continue
        lang = gather.lang_of(p)
        if lang and lang[1] == "code":
            count[lang[0]] += 1
    return [n for n, _ in sorted(count.items(), key=lambda kv: (-kv[1], kv[0]))]


def parse_version(text: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", text.split("-")[0]))


def _cmp(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    n = max(len(a), len(b))
    a, b = a + (0,) * (n - len(a)), b + (0,) * (n - len(b))
    return (a > b) - (a < b)


def _needed_min(tool: dict, scopes: set[str]) -> str | None:
    m = tool.get("min")
    if isinstance(m, dict):
        mins = [m[s] for s in scopes if s in m]
        return max(mins, key=parse_version) if mins else None
    return m


def _install_text(tool: dict) -> str:
    key = "darwin" if sys.platform.startswith("darwin") else "linux"
    return tool.get("install", {}).get(key, "")


def check_host(tool: dict, scopes: set[str], path: str | None = None) -> dict:
    need = _needed_min(tool, scopes)
    res = {"id": tool["id"], "status": "missing", "version": None, "path": None, "needs": need, "for": [],
           "install": _install_text(tool), "optional": bool(tool.get("optional"))}
    exe = shutil.which(tool["command"][0], path=path)
    if not exe:
        return res
    res["path"] = exe
    env = {**os.environ, "PATH": path} if path is not None else None
    try:
        r = subprocess.run([exe, *tool["command"][1:]], capture_output=True, text=True, timeout=15, env=env)
        found = re.findall(tool["pattern"], r.stdout + "\n" + r.stderr)
    except (OSError, subprocess.TimeoutExpired):
        found = []
    if not found:
        return res
    best = max(found, key=parse_version)
    res["version"] = best
    res["status"] = "old" if need and _cmp(parse_version(best), parse_version(need)) < 0 else "ok"
    return res


def preflight(langs: list[str], tools: dict | None = None, path: str | None = None, all_scopes: bool = False) -> dict:
    tools = tools or load_tools()
    scope_langs: dict[str, list[str]] = {"all": []}
    for lang in langs:
        s = scope_of(lang, tools)
        if s:
            scope_langs.setdefault(s, []).append(lang)
    if all_scopes:
        for t in tools["host"] + tools["tools"]:
            for s in t["scope"]:
                scope_langs.setdefault(s, [])
    scopes = set(scope_langs)
    host, status = [], {}
    for t in tools["host"]:
        if not scopes & set(t["scope"]):
            continue
        r = check_host(t, scopes & set(t["scope"]), path)
        r["for"] = sorted({l for s in t["scope"] if s in scope_langs for l in scope_langs[s]})
        host.append(r)
        status[t["id"]] = r["status"]
    selfi = []
    for t in tools["tools"]:
        if not scopes & set(t["scope"]):
            continue
        needs = [h for h in HOST_FOR_VIA[t["via"]] if status.get(h, "missing") != "ok"]
        selfi.append({"id": t["id"], "version": t["version"], "via": t["via"], "locked": bool(t.get("node_lock")), "checked": bool(t.get("nupkg")),
                      "status": "missing" if needs else "first-use", "needs": needs})
    missing = [h["id"] for h in host if h["status"] != "ok" and not h["optional"]] + [s["id"] for s in selfi if s["status"] == "missing"]
    return {"languages": [{"name": l, "tier": tier_of(l, tools)} for l in langs], "host": host,
            "self_installing": selfi, "missing": missing}


def preflight_at(top: str, sha: str, path: str | None = None) -> dict:
    """preflight for the languages at sha, plus the .NET SDK a C# repository's global.json asks for."""
    langs = languages_at(top, sha)
    report = preflight(langs, path=path)
    if "C#" in langs:
        names = subprocess.run(["git", "-C", top, "ls-tree", "-r", "--name-only", "-z", sha], capture_output=True)
        paths = [p for p in names.stdout.decode("utf-8", "replace").split("\0") if p]

        def read(p):
            r = subprocess.run(["git", "-C", top, "show", f"{sha}:{p}"], capture_output=True)
            return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None

        cs_sdk.apply(report, cs_sdk.requirements(paths, read), cs_sdk.list_sdks(path))
    return report


def format_text(report: dict) -> str:
    out = []
    langs = report["languages"]
    if langs:
        out.append("Languages: " + ", ".join(
            f"{l['name']} (full support)" if l["tier"] == "A" else f"{l['name']} (Tier B: no static graph)" for l in langs))
    else:
        out.append("Languages: none found")
    out.append("Needed on this machine:")
    for h in (h for h in report["host"] if not h.get("optional")):
        why = f", for {', '.join(h['for'])}" if h["for"] and h["status"] != "ok" else ""
        need = f"needs {h['needs']} or later" if h["needs"] else "needs no particular version"
        if h["status"] == "ok":
            out.append(f"  ok       {h['id'] + ' ' + h['version']:<16} {need}")
        elif h["status"] == "old":
            out.append(f"  TOO OLD  {h['id']} {h['version']}  {need}{why}")
            out.append(f"           Install: {h['install']}")
        else:
            out.append(f"  MISSING  {h['id']:<16} {need}{why}")
            out.append(f"           Install: {h['install']}")
    optional = [h for h in report["host"] if h.get("optional")]
    if optional:
        out.append("Optional (a build works without them):")
        purpose = {t["id"]: t.get("purpose", "") for t in load_tools()["host"]}
        for h in optional:
            if h["status"] == "ok":
                out.append(f"  ok       {h['id'] + ' ' + h['version']:<16} {purpose.get(h['id'], '')}")
            else:
                out.append(f"  not found {h['id']:<15} {purpose.get(h['id'], '')}")
                out.append(f"           Install: {h['install']}")
    selfi = report["self_installing"]
    if selfi:
        out.append("Installed by dossier on first use (pinned):")
        for s in selfi:
            ver = s["version"] or "(version open)"
            tail = f" (cannot install: needs {', '.join(s['needs'])})" if s["needs"] else ""
            how = ("from a lockfile with npm" if s.get("locked")
                   else "from a hash-checked NuGet package" if s.get("checked") else f"via {s['via']}")
            out.append(f"  {s['id']} {ver} {how}{tail}")
    n = len([m for m in report["missing"] if m in {h["id"] for h in report["host"] if h["status"] != "ok" and not h.get("optional")}])
    if n:
        out.append(f"{n} tool{' is' if n == 1 else 's are'} missing. Install {'it' if n == 1 else 'them'}, "
                   "or build with --allow-missing to carry on without them.")
    else:
        out.append("Nothing is missing.")
    return "\n".join(out)
