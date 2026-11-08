"""Turns semgrep results for the C# rules into adapter items (plan 011, D9, D14). Pure."""
from __future__ import annotations

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


def items(results: list, project_of=None, build_projects=None) -> dict:
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
