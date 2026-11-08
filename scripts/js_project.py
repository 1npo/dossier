"""JavaScript and TypeScript projects: which folders are installed and analysed as one unit. Pure, no file or process access.

A package is a folder with a `package.json`. A project is a package that is installed on its own (it holds a lockfile, or
nothing above it is a lockfile or workspace root). Other packages are members of the nearest project above them.
`tree` is the list of tracked paths and `read(path)` gives a file's text or None.
"""
from __future__ import annotations

import json

import gather

LOCKFILES = (("package-lock.json", "npm"), ("yarn.lock", "yarn"), ("pnpm-lock.yaml", "pnpm"), ("bun.lock", "bun"), ("bun.lockb", "bun"))
JS_LANGUAGES = {"JavaScript", "TypeScript"}
UNSUPPORTED = {"koa": "Koa", "hapi": "Hapi", "@hapi/hapi": "Hapi", "hono": "Hono", "nuxt": "Nuxt", "@sveltejs/kit": "SvelteKit",
               "astro": "Astro", "@angular/core": "Angular"}
UNSUPPORTED_PREFIX = {"@remix-run/": "Remix"}


def read_json(read, path: str) -> dict | None:
    text = read(path)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _join(folder: str, name: str) -> str:
    return f"{folder}/{name}" if folder else name


def _parent(folder: str) -> str:
    return folder.rsplit("/", 1)[0] if "/" in folder else ""


def _inside(path: str, folder: str) -> bool:
    return not folder or path.startswith(folder + "/")


def _is_workspace(folder: str, manifest: dict | None, tracked: set) -> bool:
    ws = (manifest or {}).get("workspaces")
    return bool(ws) or _join(folder, "pnpm-workspace.yaml") in tracked


def projects(tree, read) -> list[dict]:
    tracked = set(tree)
    packages = sorted({p.rsplit("/", 1)[0] if "/" in p else "" for p in tracked
                       if p.rsplit("/", 1)[-1] == "package.json" and gather.noise_reason(p) is None})
    info = {}
    for folder in packages:
        manifest = read_json(read, _join(folder, "package.json"))
        lock = next((l for l in LOCKFILES if _join(folder, l[0]) in tracked), None)
        info[folder] = {"manifest": manifest, "lock": lock, "workspace": _is_workspace(folder, manifest, tracked)}

    def has_root_above(folder):
        return any(a != folder and _inside(folder, a) and (info[a]["lock"] or info[a]["workspace"]) for a in packages)

    roots = [f for f in packages if info[f]["lock"] or not has_root_above(f)]
    out = {}
    for folder in roots:
        manifest, lock = info[folder]["manifest"], info[folder]["lock"]
        manager = lock[1] if lock else None
        if manager is None and manifest and isinstance(manifest.get("packageManager"), str):
            manager = manifest["packageManager"].split("@")[0] or None
        out[folder] = {"dir": folder, "package": (manifest or {}).get("name") if isinstance((manifest or {}).get("name"), str) else None,
                       "lockfile": lock[0] if lock else None, "manager": manager, "members": [], "files": []}
    def deepest(path, among):
        return max((r for r in among if path == r or _inside(path, r)), key=len, default=None)

    for folder in packages:
        owner = deepest(folder, roots)
        if owner is not None:
            out[owner]["members"].append(folder)
    for path in sorted(tracked):
        language = gather.lang_of(path)
        if not language or language[0] not in JS_LANGUAGES or gather.noise_reason(path) is not None:
            continue
        owner = deepest(path, roots)
        if owner is None:
            out.setdefault("", {"dir": "", "package": None, "lockfile": None, "manager": None, "members": [], "files": []})
            owner = ""
        out[owner]["files"].append(path)
    return [out[k] for k in sorted(out) if out[k]["files"]]


def source_roots(projs: list[dict], tree) -> list[dict]:
    """One `source-root` item per project, naming the folder that becomes its area in the graph."""
    items, tracked = [], set(tree)
    for p in projs:
        folder = p["dir"]
        if len(projs) == 1:
            root = _join(folder, "src") if any(f.startswith(_join(folder, "src") + "/") for f in p["files"]) else folder
        elif folder == "":
            continue
        else:
            root = _parent(folder) or folder
        manifest = _join(folder, "package.json")
        items.append({"kind": "source-root", "path": manifest if manifest in tracked else p["files"][0], "root": root})
    return items


def manifest_frameworks(projs: list[dict], read) -> list[str]:
    """Display names of frameworks that a manifest names and the adapter does not support, sorted."""
    found = set()
    for p in projs:
        for folder in p["members"]:
            manifest = read_json(read, _join(folder, "package.json")) or {}
            for key in ("dependencies", "devDependencies", "peerDependencies"):
                for name in (manifest.get(key) or {}):
                    if name in UNSUPPORTED:
                        found.add(UNSUPPORTED[name])
                    for prefix, shown in UNSUPPORTED_PREFIX.items():
                        if name.startswith(prefix):
                            found.add(shown)
    return sorted(found)
