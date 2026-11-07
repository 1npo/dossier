"""Installing the JavaScript and TypeScript tools from one shipped lockfile, and the Node gate.

`ensure_installed` runs `npm ci --ignore-scripts` once per (lockfile, ts_facts.mjs) pair into the shared tool cache.
`ts_facts.mjs` is copied beside `node_modules` because its import of `typescript` must resolve from there.
Every call goes through the safe runner passed in as `run` (see `sandbox.run`).
"""
from __future__ import annotations

import hashlib
import json
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


class TsFacts:
    """Client for `ts_facts.mjs`: types, exports, imports, React components and routes, read with the TypeScript compiler API."""

    def __init__(self, run, install: Path, timeout: float):
        self.run, self.install, self.timeout = run, Path(install), timeout

    def facts(self, project_dir, files: list[str]) -> dict:
        request = json.dumps({"root": ".", "files": list(files)}).encode()
        result = self.run(["node", "--max-old-space-size=4096", str(self.install / "ts_facts.mjs")], cwd=Path(project_dir), stage="js-ts-facts",
                          profile="restricted", timeout=self.timeout, input=request)
        _check(result, "Reading the TypeScript facts")
        try:
            data = json.loads(result.stdout.read_text(errors="replace"))
        except ValueError as e:
            raise ToolError(f"Reading the TypeScript facts gave output that is not JSON: {e}") from e
        if not isinstance(data, dict):
            raise ToolError("Reading the TypeScript facts gave output that is not an object.")
        return data


CRUISE_EXCLUDE = r"(^|/)(node_modules|dist|build|coverage|\.next|\.nx)/"


class DepCruiser:
    """Client for dependency-cruiser: the import graph (no repository config) and, separately, the repository's own rules."""

    def __init__(self, run, install: Path, timeout: float):
        self.run, self.timeout = run, timeout
        self.bin = str(Path(install) / "node_modules" / "dependency-cruiser" / "bin" / "dependency-cruiser.mjs")

    def _json(self, cmd, project_dir, what, stage, tolerate_exit=False) -> dict:
        result = self.run(["node", self.bin, *cmd], cwd=Path(project_dir), stage=stage, profile="restricted", timeout=self.timeout)
        if result.timed_out or (result.returncode != 0 and not tolerate_exit):
            _check(result, what)
        try:
            return json.loads(result.stdout.read_text(errors="replace"))
        except ValueError as e:
            _check(result, what)  # a failed run explains itself better than a JSON error
            raise ToolError(f"{what} gave output that is not JSON: {e}") from e

    def cruise(self, project_dir, tsconfig: str | None = None) -> dict:
        cmd = [".", "--no-config", "--output-type", "json", "--ts-pre-compilation-deps", "--no-progress", "--do-not-follow", "node_modules",
               "--exclude", CRUISE_EXCLUDE]
        if tsconfig:
            cmd += ["--ts-config", tsconfig]
        return self._json(cmd, project_dir, "Building the import graph", "js-depcruise")

    def violations(self, project_dir, config_file: str) -> list:
        """The repository's own rules. dependency-cruiser exits with the number of errors, so a non-zero exit with JSON is normal."""
        data = self._json([".", "--config", config_file, "--output-type", "json", "--no-progress", "--ts-pre-compilation-deps"], project_dir,
                          "Checking the repository's dependency rules", "js-depcruise-rules", tolerate_exit=True)
        return (data.get("summary") or {}).get("violations") or []


class Knip:
    """Client for knip (unused files, dependencies, exports and types). knip loads the repository's own config, so it runs restricted."""

    def __init__(self, run, install: Path, timeout: float):
        self.run, self.timeout = run, timeout
        self.bin = str(Path(install) / "node_modules" / "knip" / "bin" / "knip.js")

    def run_knip(self, project_dir) -> dict:
        cmd = ["node", self.bin, "--reporter", "json", "--no-exit-code", "--no-progress", "--no-config-hints", "--include", "files,dependencies,exports,types"]
        result = self.run(cmd, cwd=Path(project_dir), stage="js-knip", profile="restricted", timeout=self.timeout)
        if result.timed_out:
            raise ToolError("knip took too long and was stopped.")
        if result.returncode != 0:
            first = next((l.strip() for l in result.stderr.read_text(errors="replace").splitlines() if l.strip()), "no message")
            raise ToolError(f"knip failed (exit {result.returncode}): {first}")
        try:
            data = json.loads(result.stdout.read_text(errors="replace"))
        except ValueError as e:
            raise ToolError(f"knip printed something that is not JSON ({e}).") from e
        if not isinstance(data, dict):
            raise ToolError("knip printed something that is not an object.")
        return data


class ScipTs:
    """Client for scip-typescript: one index file per project, written outside the checkout."""

    def __init__(self, run, install: Path, timeout: float):
        self.run, self.timeout = run, timeout
        self.main = str(Path(install) / "node_modules" / "@sourcegraph" / "scip-typescript" / "dist" / "src" / "main.js")

    def index(self, project_dir, area, n: int, has_tsconfig: bool) -> Path:
        out = Path(area) / "scip"
        out.mkdir(parents=True, exist_ok=True)
        target = out / f"js-{n}.scip"
        target.unlink(missing_ok=True)
        cmd = ["node", "--max-old-space-size=4096", self.main, "index", "--no-progress-bar", "--output", str(target)]
        if not has_tsconfig:
            cmd.append("--infer-tsconfig")
        _check(self.run(cmd, cwd=Path(project_dir), stage="js-scip", profile="restricted", timeout=self.timeout), "scip-typescript")
        if not target.is_file() or target.stat().st_size == 0:
            raise ToolError("scip-typescript finished without writing an index.")
        return target
