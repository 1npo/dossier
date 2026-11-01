"""Clients for the two locked workers (tree-sitter and semgrep) that every adapter shares.

Each call starts a worker through the safe runner (profile "tool"), sends one JSON request on stdin
and reads one JSON response from the worker's stdout file.
"""
from __future__ import annotations

import json
from pathlib import Path

import toolcheck

SCRIPTS = Path(__file__).resolve().parent


class ToolError(RuntimeError):
    pass


def _call(run, tool: str, worker: str, request: dict) -> dict:
    py = toolcheck.load_tools()["python"]
    cmd = ["uv", "run", "--locked", "--python", py, "--script", str(SCRIPTS / worker)]
    result = run(cmd, input=json.dumps(request).encode(), stage=tool, profile="tool")
    if result.timed_out:
        raise ToolError(f"{tool} took too long and was stopped.")
    if result.returncode != 0:
        tail = "\n".join(result.stderr.read_text(errors="replace").splitlines()[-20:])
        raise ToolError(f"{tool} failed (exit {result.returncode}):\n{tail}")
    try:
        return json.loads(result.stdout.read_text())
    except ValueError as e:
        raise ToolError(f"{tool} printed something that is not JSON ({e}).")


class TreeSitter:
    def __init__(self, run):
        self.run = run

    def query(self, language: str, paths: list[str], query: str) -> list[dict]:
        res = _call(self.run, "treesitter", "ts_worker.py", {"language": language, "paths": paths, "query": query})
        return res["matches"]


class Semgrep:
    def __init__(self, run):
        self.run = run

    def scan(self, config: Path, paths: list[str] | None = None, timeout: int = 30) -> list[dict]:
        res = _call(self.run, "semgrep", "semgrep_worker.py",
                    {"config": str(Path(config).resolve()), "paths": paths, "timeout": timeout})
        return res["results"]
