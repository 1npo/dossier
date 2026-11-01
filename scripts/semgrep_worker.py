# /// script
# requires-python = ">=3.10"
# dependencies = ["semgrep==1.181.0"]
# ///
"""Semgrep worker: reads one JSON request on stdin, prints one JSON response on stdout.

Request:  {"config": "/abs/rules", "paths": null, "timeout": 30}
Response: {"results": [{"rule", "path", "start_line", "end_line", "message", "snippet", "metadata"}], "errors": [...]}
Runs the semgrep installed next to this interpreter, in the current directory, with metrics off and no login.
"""
import json
import subprocess
import sys
from pathlib import Path


def rule_id(check_id: str, config: str) -> str:
    """Semgrep prefixes ids with the rule file's folder (dots for slashes); our ids start with 'dossier.'."""
    prefix = config.strip("/").replace("/", ".") + "."
    rest = check_id[len(prefix):] if check_id.startswith(prefix) else check_id
    i = rest.find("dossier.")
    return rest[i:] if i >= 0 else rest


def main() -> None:
    req = json.load(sys.stdin)
    cmd = [str(Path(sys.executable).parent / "semgrep"), "scan", "--config", req["config"], "--json", "--metrics=off",
           "--disable-version-check", "--oss-only", "--quiet", "--timeout", str(req.get("timeout", 30)),
           *(req.get("paths") or [])]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode not in (0, 1):
        sys.stderr.write(r.stderr)
        sys.exit(r.returncode)
    data = json.loads(r.stdout)
    results = [{"rule": rule_id(x["check_id"], req["config"]), "path": x["path"], "start_line": x["start"]["line"], "end_line": x["end"]["line"],
                "message": x["extra"].get("message"), "snippet": x["extra"].get("lines"), "metadata": x["extra"].get("metadata", {})}
               for x in data.get("results", [])]
    json.dump({"results": results, "errors": data.get("errors", [])}, sys.stdout)


if __name__ == "__main__":
    main()
