# /// script
# requires-python = ">=3.10"
# dependencies = ["semgrep==1.181.0"]
# ///
"""Semgrep worker: reads one JSON request on stdin, prints one JSON response on stdout.

Request:  {"config": "/abs/rules", "paths": null, "timeout": 30}
Response: {"results": [{"rule", "path", "start_line", "end_line", "message", "snippet", "detail", "metadata"}], "errors": [...]}
Test:     {"test": true, "config": "/abs/rules", "targets": "/abs/tests"} -> {"returncode", "output"}
Runs the semgrep installed next to this interpreter, in the current directory, with metrics off and no login.
Pass explicit file paths: semgrep skips folders such as `tests/` and `vendor/` on its own when it walks the current
directory, but it always scans a file named on the command line. Long lists are sent in batches.

Without a login semgrep blanks the matched text ("requires login") and returns no metavariables, so the worker reads
the match from the source file: `snippet` is the source line where the match starts (at most 200 characters) and `detail`
is the first group of the regular expression in the rule's `metadata.detail`, applied to the matched text (or null).
"""
import json
import re
import subprocess
import sys
from pathlib import Path


def rule_id(check_id: str, config: str) -> str:
    """Semgrep prefixes ids with the rule file's folder (dots for slashes); our ids start with 'dossier.'."""
    prefix = config.strip("/").replace("/", ".") + "."
    rest = check_id[len(prefix):] if check_id.startswith(prefix) else check_id
    i = rest.find("dossier.")
    return rest[i:] if i >= 0 else rest


CHUNK = 400


def chunked(paths, size: int = CHUNK) -> list:
    """Batches of at most `size` paths; one empty batch (scan the current directory) when there are none."""
    paths = list(paths or [])
    return [paths[i:i + size] for i in range(0, len(paths), size)] or [[]]


def matched_text(path: str, start: int, end: int) -> str:
    """The text between two byte offsets of a file in the current directory; empty when it cannot be read."""
    try:
        return Path(path).read_bytes()[start:end].decode("utf-8", errors="replace")
    except OSError:
        return ""


def source_line(path: str, line: int) -> str:
    """The stripped source line (1-based) of a file in the current directory, at most 200 characters; empty if unreadable."""
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return lines[line - 1].strip()[:200] if 0 < line <= len(lines) else ""


def detail_of(text: str, pattern) -> "str | None":
    """First group of `pattern` found in `text`, or None (no pattern, no match, or a bad pattern)."""
    if not pattern:
        return None
    try:
        m = re.search(pattern, text)
    except re.error:
        return None
    return m.group(1) if m and m.groups() else None


def run_test(req: dict) -> None:
    cmd = [str(Path(sys.executable).parent / "semgrep"), "--test", "--config", req["config"], "--metrics=off",
           "--disable-version-check", req["targets"]]
    r = subprocess.run(cmd, capture_output=True, text=True)
    json.dump({"returncode": r.returncode, "output": r.stdout + r.stderr}, sys.stdout)


def scan(req: dict) -> dict:
    results, errors = [], []
    for batch in chunked(req.get("paths")):
        cmd = [str(Path(sys.executable).parent / "semgrep"), "scan", "--config", req["config"], "--json", "--metrics=off",
               "--disable-version-check", "--oss-only", "--quiet", "--timeout", str(req.get("timeout", 30)), *batch]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode not in (0, 1):
            sys.stderr.write(r.stderr)
            sys.exit(r.returncode)
        data = json.loads(r.stdout)
        errors += data.get("errors", [])
        for x in data.get("results", []):
            text = matched_text(x["path"], x["start"]["offset"], x["end"]["offset"])
            meta = x["extra"].get("metadata", {})
            results.append({"rule": rule_id(x["check_id"], req["config"]), "path": x["path"], "start_line": x["start"]["line"],
                            "end_line": x["end"]["line"], "message": x["extra"].get("message"),
                            "snippet": source_line(x["path"], x["start"]["line"]), "detail": detail_of(text, meta.get("detail")),
                            "metadata": meta})
    return {"results": results, "errors": errors}


def main() -> None:
    req = json.load(sys.stdin)
    if req.get("test"):
        return run_test(req)
    json.dump(scan(req), sys.stdout)


if __name__ == "__main__":
    main()
