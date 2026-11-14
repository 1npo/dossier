"""Where the package finds its files: the data shipped inside it and the skill folder around it.

Every file the code reads by path (card schemas, rules, page assets, vendored bundles, workers,
Node helper projects, tools.json, eol.json) comes from `data()`. No other module in the package
builds a path from `__file__`; tests/content/test_layers.py enforces that.
"""
from __future__ import annotations

import os
import sys
from importlib.resources import files
from pathlib import Path

__all__ = ["data", "ensure_utf8", "skill_root", "version"]


def ensure_utf8() -> None:
    """Make output UTF-8 whatever the console is. On Windows a piped stdout is cp1252, and printing a character such as
    an arrow then raises UnicodeEncodeError. Child Python processes inherit PYTHONUTF8."""
    os.environ.setdefault("PYTHONUTF8", "1")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def data(*parts: str) -> Path:
    """The path of a file or folder under `dossier/data/`.

    The package is always a folder on disk (a clone, a plugin copy or an editable install), so the
    result is a real path that can be handed to semgrep, uv or npm.
    """
    root = files("dossier").joinpath("data", *parts)
    if not isinstance(root, Path):
        raise RuntimeError(f"dossier: package data is not on disk ({root!r}); run dossier from a clone")
    return root


def skill_root() -> Path:
    """The skill folder: the one holding SKILL.md, VERSION, scripts/ and src/."""
    root = Path(__file__).resolve().parents[2]
    if not (root / "SKILL.md").is_file():
        raise RuntimeError(f"dossier: no SKILL.md in {root}; run dossier from a clone of the skill")
    return root


def version() -> str:
    """The skill's version, from VERSION at the skill root."""
    return (skill_root() / "VERSION").read_text(encoding="utf-8").strip()
