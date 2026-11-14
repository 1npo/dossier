"""Helpers every command uses: the skill root, version and config path, JSON load and save, the state
file, the dossier home, and where one repository's output folder is. Reads and writes only the files it
is given. Commands call these as `common.name`, so a test can patch one in a single place.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import re
import subprocess
import sys

from dossier import resources
from dossier.core import config
from dossier.findings import resolve
from typing import Any, NoReturn

__all__ = [
    "ROOT", "VERSION", "die", "get_home", "load", "load_state", "now", "out_dir", "save", "save_state", "toplevel",
]


ROOT = resources.skill_root()


VERSION = resources.version()


CONFIG = config.path()


def die(msg: str, code: int = 1) -> NoReturn:
    print(msg, file=sys.stderr)
    sys.exit(code)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path: Path | str, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as exc:
        die(f"{path} is not valid JSON: {exc}")


def save(path: Path | str, data: Any) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def load_state(out: Path) -> dict:
    return resolve.migrate(load(out / "state.json", {}) or {})


def save_state(out: Path, state: dict) -> None:
    """Write state.json. When the skill version changes, keep a copy of the old file first."""
    old = out / "state.json"
    prev = state.get("skill_version")
    if old.exists() and prev and prev != VERSION:
        keep = out / f"state.backup-v{prev}.json"
        if not keep.exists():
            keep.write_text(old.read_text(), encoding="utf-8")
    state["skill_version"] = VERSION
    save(old, state)


def get_home() -> Path:
    h = config.home()
    if not h:
        die("No dossier home is set. Run /dossier home <directory> to choose where dossiers are saved.")
    return h


def toplevel(repo_arg: str | None) -> str:
    p = Path(repo_arg or ".").expanduser().resolve()
    r = subprocess.run(["git", "-C", str(p), "rev-parse", "--show-toplevel"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        die(f"'{p}' is not inside a git repository.")
    return r.stdout.strip()


def root_commit(top):
    out = subprocess.run(["git", "-C", top, "rev-list", "--max-parents=0", "HEAD"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.split()
    return sorted(out)[0] if out else ""


def out_dir(top: str) -> tuple[Path, str, str]:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(top).name) or "repo"
    root = root_commit(top)
    d = get_home() / name
    st = load(d / "state.json")
    if st and st.get("repo", {}).get("root_commit") not in (None, "", root):
        d = get_home() / f"{name}-{root[:6]}"   # another repository already uses this name
    return d, name, root
