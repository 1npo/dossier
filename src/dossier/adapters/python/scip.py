"""Installing and running scip-python from a committed lockfile.

The install happens once into the shared tool cache with `npm ci --ignore-scripts`, so no transitive package floats.
Every call goes through the safe runner passed in as `run` (see `sandbox.run`).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import warnings
from pathlib import Path

from dossier import resources
from dossier.tooling.sandbox import WINDOWS
from dossier.tooling import shared_tools
from dossier.tooling.shared_tools import ToolError
from collections.abc import Callable

__all__ = ["ensure_installed", "run_index", "patch_windows_bundle"]

NODE_DIR = resources.data("node", "scip-python")
BUNDLE = Path("node_modules") / "@sourcegraph" / "scip-python" / "dist" / "scip-python.js"
# scip-python up to 0.6.8 builds a RegExp from path.sep, which is a lone backslash (an invalid pattern) on Windows.
BUGGY_SEP = 'new RegExp(o.sep,"g")'
FIXED_SEP = 'new RegExp(o.sep.replace(/[.*+?^${}()|[\\]\\\\]/g,"\\\\$&"),"g")'
INDEX_JS = Path("node_modules") / "@sourcegraph" / "scip-python" / "index.js"


def install_dir(cache_root, version: str) -> Path:
    return Path(cache_root) / ".dossier-tools" / "node" / f"scip-python-{version}"


def _lock_sha() -> str:
    return hashlib.sha1((NODE_DIR / "package-lock.json").read_bytes()).hexdigest()


def patch_windows_bundle(text: str) -> str | None:
    """The bundle text with the path-separator regex escaped, or None when the exact original is not there exactly once."""
    return text.replace(BUGGY_SEP, FIXED_SEP) if text.count(BUGGY_SEP) == 1 else None


def _patch_install(folder: Path) -> bool:
    """Windows only: patch the installed bundle once, keeping a `.orig` copy. True when a patch was applied."""
    if not WINDOWS:
        return False
    bundle = folder / BUNDLE
    if not bundle.is_file():
        return False
    patched = patch_windows_bundle(bundle.read_text(encoding="utf-8"))
    if patched is None:
        return False
    orig = bundle.with_name(bundle.name + ".orig")
    if not orig.exists():
        shutil.copyfile(bundle, orig)
    bundle.write_text(patched, encoding="utf-8", newline="")
    warnings.warn("Applied a Windows patch to scip-python (escaped the path separator in its regular expression); the original is kept as scip-python.js.orig.")
    return True


def ensure_installed(run: Callable, cache_root: Path, version: str, timeout: float) -> Path:
    """Run `npm ci` once per lockfile (a marker file holds the lock's sha1). Returns the path of index.js."""
    folder = install_dir(cache_root, version)
    marker, index = folder / ".installed", folder / INDEX_JS
    if marker.exists() and marker.read_text(encoding="utf-8").strip() == _lock_sha() and index.exists():
        _patch_install(folder)   # an install made before the patch existed; a no-op once patched
        return index
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("package.json", "package-lock.json"):
        shutil.copyfile(NODE_DIR / name, folder / name)
    shared_tools.check_result(run(["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=folder, stage="scip-install", profile="tool",
               timeout=timeout), "Installing scip-python")
    if not index.exists():
        raise ToolError("Installing scip-python finished, but its program file is missing.")
    _patch_install(folder)
    marker.write_text(_lock_sha() + "\n", encoding="utf-8")
    return index


def environment(checkout, venv=None) -> list:
    """The packages installed in `venv` (default `<checkout>/.venv`) as [{"name", "version", "files"}]; [] when there is none."""
    found = []
    venv = Path(venv) if venv else Path(checkout) / ".venv"
    for dist in sorted(venv.glob("lib/python*/site-packages/*.dist-info")):
        meta = (dist / "METADATA")
        if not meta.is_file():
            continue
        text = meta.read_text(encoding="utf-8", errors="replace")
        name, version = re.search(r"^Name:\s*(\S+)", text, re.M), re.search(r"^Version:\s*(\S+)", text, re.M)
        if not (name and version):
            continue
        record = dist / "RECORD"
        files = [line.split(",")[0] for line in record.read_text(encoding="utf-8", errors="replace").splitlines() if line] if record.is_file() else []
        found.append({"name": name.group(1), "version": version.group(1), "files": files})
    return found


def run_index(run: Callable, index_js: str, checkout: Path, area: Path, repo_name: str, sha: str, timeout: float, cwd: Path | None = None, project_name: str | None = None, venv: Path | str | None = None) -> Path:
    """Index the checkout, or the project folder `cwd` inside it. The index and the environment file go into `<area>/scip/`."""
    out = Path(area) / "scip"
    out.mkdir(parents=True, exist_ok=True)
    index, env_file = out / "index.scip", out / "env.json"
    index.unlink(missing_ok=True)
    env_file.write_text(json.dumps(environment(checkout, venv)), encoding="utf-8")
    cmd = ["node", str(index_js), "index", ".", "--project-name", project_name or repo_name, "--project-version", sha, "--output", str(index),
           "--quiet", "--environment", str(env_file)]
    extra = {"cwd": cwd} if cwd else {}
    shared_tools.check_result(run(cmd, stage="scip-python", profile="restricted", timeout=timeout, **extra), "scip-python")
    if not index.is_file() or index.stat().st_size == 0:
        raise ToolError("scip-python finished without writing an index.")
    return index
