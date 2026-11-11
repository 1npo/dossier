"""Installing and running scip-python from a committed lockfile.

The install happens once into the shared tool cache with `npm ci --ignore-scripts`, so no transitive package floats.
Every call goes through the safe runner passed in as `run` (see `sandbox.run`).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

from shared_tools import SCRIPTS, ToolError

NODE_DIR = SCRIPTS / "node" / "scip-python"
INDEX_JS = Path("node_modules") / "@sourcegraph" / "scip-python" / "index.js"


def install_dir(cache_root, version: str) -> Path:
    return Path(cache_root) / ".dossier-tools" / "node" / f"scip-python-{version}"


def _lock_sha() -> str:
    return hashlib.sha1((NODE_DIR / "package-lock.json").read_bytes()).hexdigest()


def _check(result, what: str) -> None:
    if result.timed_out:
        raise ToolError(f"{what} took too long and was stopped.")
    if result.returncode != 0:
        tail = "\n".join(result.stderr.read_text(errors="replace").splitlines()[-20:])
        raise ToolError(f"{what} failed (exit {result.returncode}):\n{tail}")


def ensure_installed(run, cache_root, version: str, timeout: float) -> Path:
    """Run `npm ci` once per lockfile (a marker file holds the lock's sha1). Returns the path of index.js."""
    folder = install_dir(cache_root, version)
    marker, index = folder / ".installed", folder / INDEX_JS
    if marker.exists() and marker.read_text().strip() == _lock_sha() and index.exists():
        return index
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("package.json", "package-lock.json"):
        shutil.copyfile(NODE_DIR / name, folder / name)
    _check(run(["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=folder, stage="scip-install", profile="tool",
               timeout=timeout), "Installing scip-python")
    if not index.exists():
        raise ToolError("Installing scip-python finished, but its program file is missing.")
    marker.write_text(_lock_sha() + "\n")
    return index


def environment(checkout, venv=None) -> list:
    """The packages installed in `venv` (default `<checkout>/.venv`) as [{"name", "version", "files"}]; [] when there is none."""
    found = []
    venv = Path(venv) if venv else Path(checkout) / ".venv"
    for dist in sorted(venv.glob("lib/python*/site-packages/*.dist-info")):
        meta = (dist / "METADATA")
        if not meta.is_file():
            continue
        text = meta.read_text(errors="replace")
        name, version = re.search(r"^Name:\s*(\S+)", text, re.M), re.search(r"^Version:\s*(\S+)", text, re.M)
        if not (name and version):
            continue
        record = dist / "RECORD"
        files = [line.split(",")[0] for line in record.read_text(errors="replace").splitlines() if line] if record.is_file() else []
        found.append({"name": name.group(1), "version": version.group(1), "files": files})
    return found


def run_index(run, index_js, checkout, area, repo_name: str, sha: str, timeout: float, cwd=None, project_name=None, venv=None) -> Path:
    """Index the checkout, or the project folder `cwd` inside it. The index and the environment file go into `<area>/scip/`."""
    out = Path(area) / "scip"
    out.mkdir(parents=True, exist_ok=True)
    index, env_file = out / "index.scip", out / "env.json"
    index.unlink(missing_ok=True)
    env_file.write_text(json.dumps(environment(checkout, venv)))
    cmd = ["node", str(index_js), "index", ".", "--project-name", project_name or repo_name, "--project-version", sha, "--output", str(index),
           "--quiet", "--environment", str(env_file)]
    extra = {"cwd": cwd} if cwd else {}
    _check(run(cmd, stage="scip-python", profile="restricted", timeout=timeout, **extra), "scip-python")
    if not index.is_file() or index.stat().st_size == 0:
        raise ToolError("scip-python finished without writing an index.")
    return index
