"""Installing the JavaScript and TypeScript tools from one shipped lockfile, and the Node gate.

`ensure_installed` runs `npm ci --ignore-scripts` once per (lockfile, ts_facts.mjs) pair into the shared tool cache.
`ts_facts.mjs` is copied beside `node_modules` because its import of `typescript` must resolve from there.
Every call goes through the safe runner passed in as `run` (see `sandbox.run`).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import toolcheck
from scip_tool import _check
from shared_tools import SCRIPTS, ToolError

NODE_DIR = SCRIPTS / "node" / "js-tools"
FILES = ("package.json", "package-lock.json", "ts_facts.mjs")
PROBE = Path("node_modules") / "knip" / "bin" / "knip.js"
NOT_TRUSTED = "The ref is not trusted, so Node tools did not run. Use --allow-ref to run them."


def _lock_sha() -> str:
    return hashlib.sha1((NODE_DIR / "package-lock.json").read_bytes()).hexdigest()


def _marker_text() -> str:
    h = hashlib.sha1()
    for name in ("package-lock.json", "ts_facts.mjs"):
        h.update((NODE_DIR / name).read_bytes())
    return h.hexdigest()


def install_dir(cache_root, lock_sha: str) -> Path:
    return Path(cache_root) / ".dossier-tools" / "node" / f"js-tools-{lock_sha[:8]}"


def ensure_installed(run, cache_root, timeout: float) -> Path:
    """Install once per lockfile and script. Returns the install folder, which holds `node_modules` and `ts_facts.mjs`."""
    folder = install_dir(cache_root, _lock_sha())
    marker = folder / ".installed"
    if marker.exists() and marker.read_text().strip() == _marker_text() and (folder / PROBE).exists():
        return folder
    folder.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        (folder / name).write_bytes((NODE_DIR / name).read_bytes())
    _check(run(["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=folder, stage="js-install", profile="tool",
               timeout=timeout), "Installing the JavaScript tools")
    if not (folder / PROBE).exists():
        raise ToolError("Installing the JavaScript tools finished, but their program files are missing.")
    marker.write_text(_marker_text() + "\n")
    return folder


def node_problem(run) -> str | None:
    """None when Node is new enough, else the sentence to record as the reason the Node tools were skipped."""
    result = run(["node", "--version"], stage="node-version", profile="tool", timeout=15)
    found = None if result.timed_out or result.returncode != 0 else re.search(r"v(\d+\.\d+\.\d+)", result.stdout.read_text(errors="replace"))
    if not found:
        return "Node is not installed."
    node = next(h for h in toolcheck.load_tools()["host"] if h["id"] == "node")
    minimum = node["min"]["js"]
    if toolcheck.parse_version(found.group(1)) < toolcheck.parse_version(minimum):
        return f"Node {found.group(1)} is too old; these tools need {minimum} or later."
    return None
