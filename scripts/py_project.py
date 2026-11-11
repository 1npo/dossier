"""Which folders of a repository are Python projects, and which tracked `.py` files belong to each.

Pure functions over the set of tracked paths. Standard library only. The root folder (`""`) is always a project.
A nested project is a folder with a Python manifest, outside noise and test folders, that owns at least one
non-test `.py` file that no deeper project claims.
"""
from __future__ import annotations

import gather

MANIFESTS = ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt")


def _usable(path: str) -> bool:
    return not gather.noise_reason(path)


def _parent(folder: str) -> str:
    return folder.rpartition("/")[0]


def _owner(path: str, folders: set) -> str:
    """The deepest project folder at or above the file."""
    folder = _parent(path)
    while folder and folder not in folders:
        folder = _parent(folder)
    return folder


def projects(tree, read=None) -> list:
    """Python projects as `[{"dir", "manifests", "files"}]`, root first, then by folder name.

    `read` is accepted for symmetry with the other readers and is not used: a manifest's presence is enough.
    """
    tracked = sorted(tree)
    manifests = {}
    for p in tracked:
        folder, _, base = p.rpartition("/")
        if base in MANIFESTS and (not folder or (_usable(p) and not gather.TEST_RE.search(p))):
            manifests.setdefault(folder, []).append(p)
    files = [p for p in tracked if p.endswith(".py") and _usable(p)]
    folders = set(manifests) - {""}
    while True:
        owned = {f: 0 for f in folders}
        for p in files:
            owner = _owner(p, folders)
            if owner and not gather.TEST_RE.search(p) and not p.endswith("/setup.py"):
                owned[owner] += 1
        empty = {f for f, n in owned.items() if not n}
        if not empty:
            break
        folders -= empty
    found = {f: [] for f in sorted(folders | {""})}
    for p in files:
        found[_owner(p, folders)].append(p)
    return [{"dir": f, "manifests": manifests.get(f, []), "files": found[f]} for f in found]
