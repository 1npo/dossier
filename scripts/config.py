"""The dossier home config: one JSON file, owned by this module.

Keys: home, cache_dir, registry_auth, timeouts. Standard library only.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_TIMEOUTS = {"restore": 900, "extract": 1800, "tool": 600, "history": 600, "github": 300}


def path() -> Path:
    return Path(os.environ.get("DOSSIER_CONFIG") or Path.home() / ".config" / "dossier" / "config.json")


def load() -> dict:
    p = path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SystemExit(f"The dossier config file {p} is not valid JSON ({e}). Fix or delete it.")
    if not isinstance(data, dict):
        raise SystemExit(f"The dossier config file {p} must hold a JSON object. Fix or delete it.")
    return data


def update(**keys) -> dict:
    p = path()
    data = {**load(), **keys}
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, p)
    return data


def home() -> Path | None:
    h = os.environ.get("DOSSIER_HOME") or load().get("home")
    return Path(h).expanduser() if h else None


def cache_root() -> Path:
    c = os.environ.get("DOSSIER_CACHE") or load().get("cache_dir")
    return Path(c).expanduser() if c else Path.home() / ".local" / "cache" / "dossier"


def timeouts() -> dict:
    out = dict(DEFAULT_TIMEOUTS)
    given = load().get("timeouts", {})
    if not isinstance(given, dict):
        raise SystemExit(f"timeouts in {path()} must be an object such as {{\"restore\": 900}}.")
    for k, v in given.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
            raise SystemExit(f"timeouts.{k} in {path()} must be a positive number of seconds.")
        out[k] = v
    return out


def registry_auth() -> dict[str, list[str]]:
    auth = load().get("registry_auth", {})
    if not isinstance(auth, dict):
        raise SystemExit(f"registry_auth in {path()} must be an object that maps an ecosystem to a list of names.")
    for eco, names in auth.items():
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
            raise SystemExit(f"registry_auth.{eco} in {path()} must be a list of strings.")
    return auth
