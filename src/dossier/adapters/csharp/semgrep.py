"""Turns semgrep results for the C# rules into adapter items (plan 011, D9, D14). Pure."""
from __future__ import annotations

import json
import re

TRIGGERS = {"http-route": "a web request to `{name}`", "signalr-hub": "a SignalR connection to `{name}`", "grpc-service": "a gRPC call to `{name}`",
            "hosted-service": "when the host starts", "scheduled-job": "a schedule", "cli-command": "the `{name}` command",
            "build-target": "running `dotnet run --project {project} -- {name}`"}
ROUTE_RE = re.compile(r'^Map(Get|Post|Put|Delete|Patch|Methods)?\(\s*"(.*)$', re.S)
FALLBACK = "ANY (fallback)"


def route_name(detail: str | None, snippet: str) -> str:
    """`GET /health` from the captured `MapGet("/health`; `ANY /x` for `Map` and `MapMethods`."""
    if not detail:
        return snippet
    if detail.startswith("MapFallback"):
        return FALLBACK
    found = ROUTE_RE.match(detail)
    if not found:
        return snippet
    verb = found.group(1)
    return f"{verb.upper() if verb and verb != 'Methods' else 'ANY'} {found.group(2)}"


TARGET_NAME_RE = re.compile(r'Target\(\s*"([^"]*)"')


def _target_name(read, path: str, line: int):
    """The first string literal after `Target(` in the 5 lines from `line`, for a target whose name sits on a later line than the call."""
    text = read(path) if read else None
    if not text:
        return None
    found = TARGET_NAME_RE.search("\n".join(text.splitlines()[line - 1:line + 4]))
    return found.group(1) if found else None


def items(results: list, project_of=None, build_projects=None, read=None) -> dict:
    """{"entry_points": [...], "io_candidates": [...], "blindspots": [...]} from `Semgrep.scan` results.

    `project_of(path)` names the project file a source file belongs to. A `build-target` is kept only in a project in `build_projects`
    (when that is given). A named request header gets one row however often it is read."""
    out = {"entry_points": [], "io_candidates": [], "blindspots": []}
    headers = set()
    for r in results:
        meta, family = r["metadata"], r["rule"].split(".")[2]
        base = {"path": r["path"], "line": r["start_line"], "end_line": r["end_line"], "rule": r["rule"], "snippet": r["snippet"]}
        if family == "blindspot":
            out["blindspots"].append({**base, "pattern": meta.get("pattern")})
        elif family == "entry":
            kind = meta["kind"]
            name = route_name(r.get("detail"), r["snippet"]) if kind == "http-route" else r.get("detail") or r["snippet"]
            if kind == "build-target" and (not name or name == r["snippet"]):
                name = _target_name(read, r["path"], r["start_line"]) or name
            project = project_of(r["path"]) if project_of else None
            if kind == "build-target" and build_projects is not None and project not in build_projects:
                continue
            if kind == "http-route":
                base["snippet"] = name
            out["entry_points"].append({**base, "kind": kind, "name": name, "trigger": TRIGGERS[kind].format(name=name, project=project or "."), "target": r["path"]})
        else:
            if meta["category"] == "request-header" and r.get("detail"):
                key = r["detail"].lower()
                if key in headers:
                    continue
                headers.add(key)
            out["io_candidates"].append({**base, "category": meta["category"], "detail": r.get("detail")})
    return out


def config_inputs(tree, read) -> list:
    """`io_candidates` from files, not code: each tracked `appsettings*.json` is a config file, and each environment variable named in a
    launch profile (`Properties/launchSettings.json`) is an environment variable (D14)."""
    rows = []
    for path in tree:
        name = path.rsplit("/", 1)[-1]
        if re.fullmatch(r"appsettings(\..+)?\.json", name, re.I):
            rows.append({"path": path, "line": 1, "end_line": 1, "rule": "cs.appsettings", "snippet": name, "category": "config-file", "detail": name})
        elif path.lower().endswith("properties/launchsettings.json"):
            rows += _launch_variables(path, read(path))
    return rows


def _launch_variables(path: str, text) -> list:
    try:
        profiles = json.loads(text or "").get("profiles", {})
        names = [k for p in profiles.values() for k in (p.get("environmentVariables") or {})]
    except (ValueError, AttributeError, TypeError):
        return []
    lines = text.splitlines()
    rows = []
    for key in dict.fromkeys(names):
        line = next((n for n, t in enumerate(lines, 1) if f'"{key}"' in t), 1)
        rows.append({"path": path, "line": line, "end_line": line, "rule": "cs.launch-env", "snippet": f'"{key}"', "category": "env-var", "detail": key})
    return rows
