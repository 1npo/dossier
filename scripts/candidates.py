"""Candidate findings from the extractors: stable ids, groups and loading `extract/*.json`.

Every tool finding that a report must decide about (kept, merged or dismissed) gets an id that survives line
shifts. Standard library only: `adapters` imports this module.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ID_OUTPUTS = {"entry_points": "ep", "io_candidates": "io", "models": "md", "dead": "dd", "blindspots": "bs"}


def norm(s: str) -> str:
    """Collapse runs of whitespace to one space and strip."""
    return re.sub(r"\s+", " ", s or "").strip()


def _sha(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def _rule(item: dict) -> str:
    return item.get("rule") or item.get("kind") or ""


def _sort_key(item: dict) -> tuple:
    return (item.get("path", ""), item.get("line") or 0, _rule(item), item.get("name") or "")


def assign_ids(output: str, items: list) -> list:
    """Return new item dicts with `id` and `group` (D2), sorted by (path, line, rule or kind, name)."""
    prefix = ID_OUTPUTS[output]
    ordered = sorted(items, key=_sort_key)
    seen: dict = {}
    result = []
    for it in ordered:
        rule = _rule(it)
        snippet = it["snippet"] if it.get("snippet") else it.get("name", "")
        key = f"{rule}\0{it['path']}\0{norm(snippet)}"
        n = seen.get(key, 0)
        seen[key] = n + 1
        ident = _sha(key + "\0" + str(n))
        group = _sha(rule + "\0" + it["path"])
        result.append({**it, "id": prefix + "-" + ident, "group": prefix + "g-" + group})
    return result


def load(out) -> dict:
    """{output: items of every adapter, in adapter-name order}. Outputs with no file are left out."""
    loaded = {}
    for f in sorted((Path(out) / "extract").glob("*.json")):
        o = f.stem
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        loaded[o] = [it for name in sorted(data.get("adapters", {})) for it in data["adapters"][name].get("items", [])]
    return loaded


def by_id(extract: dict) -> dict:
    """Item ids and group ids -> item (a group maps to its first item)."""
    found = {}
    for items in extract.values():
        for it in items:
            if "id" in it:
                found[it["id"]] = it
                found.setdefault(it["group"], it)
    return found


def group_members(extract: dict) -> dict:
    """Group id -> the ids of its items."""
    members: dict = {}
    for items in extract.values():
        for it in items:
            if "id" in it:
                members.setdefault(it["group"], []).append(it["id"])
    return members
