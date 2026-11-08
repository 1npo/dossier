"""Turns semgrep results for the JavaScript rules into adapter items (plan 010, D6, D10). Pure."""
from __future__ import annotations

import js_reduce

TRIGGERS = {"cli-command": "the `{name}` command", "http-route": "a web request to `{name}`", "queue-consumer": "a message for the task `{name}`",
            "scheduled-job": "a schedule", "server-listen": "when the server starts"}
SCANNED = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")


def scannable(files: list) -> tuple:
    """(files semgrep reads, files it silently skips). `.d.ts` is left out; `.mts` and `.cts` are not parsed by these rules."""
    ok = [f for f in files if f.endswith(SCANNED) and not f.endswith(".d.ts")]
    skipped = [f for f in files if f.endswith((".mts", ".cts")) and not f.endswith((".d.mts", ".d.cts"))]
    return ok, skipped


def _route_name(detail: str | None, snippet: str) -> str:
    if not detail:
        return snippet
    method, path = js_reduce.route_parts(detail)
    return f"{method} {path}" if method else path


def items(results: list) -> dict:
    """{"entry_points": [...], "io_candidates": [...], "blindspots": [...]} from `Semgrep.scan` results.

    A named request header gets one row however often it is read (header names ignore case)."""
    out = {"entry_points": [], "io_candidates": [], "blindspots": []}
    headers = set()
    for r in results:
        meta, family = r["metadata"], r["rule"].split(".")[2]
        base = {"path": r["path"], "line": r["start_line"], "end_line": r["end_line"], "rule": r["rule"], "snippet": r["snippet"]}
        if family == "blindspot":
            out["blindspots"].append({**base, "pattern": meta.get("pattern")})
        elif family == "entry":
            kind = meta["kind"]
            if r["rule"].endswith(".entry.static-files"):
                name = "static files"
                base["snippet"] = name
            elif kind == "http-route":
                name = _route_name(r.get("detail"), r["snippet"])
                base["snippet"] = name
            elif kind == "server-listen":
                name = "listen"
            else:
                name = r.get("detail") or r["snippet"]
            out["entry_points"].append({**base, "kind": kind, "name": name, "trigger": TRIGGERS[kind].format(name=name), "target": r["path"]})
        else:
            if meta["category"] == "request-header" and r.get("detail"):
                key = r["detail"].lower()
                if key in headers:
                    continue
                headers.add(key)
            out["io_candidates"].append({**base, "category": meta["category"], "detail": r.get("detail")})
    return out
