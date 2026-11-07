"""Entry points read from project files: package bins, scripts and main, Nx targets and Next.js file routes. Pure.

`read(path)` gives a file's text or None. Lines are found by key name, because the JSON is read as data and has no positions.
"""
from __future__ import annotations

import posixpath

import gather
import js_project

CODE_EXT = (".js", ".jsx", ".ts", ".tsx")
NEXT_SPECIAL = {"_app", "_document", "_error"}


def _join(folder: str, name: str) -> str:
    return f"{folder}/{name}" if folder else name


def _line_of(lines: list, section: str | None, key: str) -> int:
    """1-based line of `"key"`, searched after the line of `"section"` when one is given; the section's line if the key is not found."""
    start = 0
    if section:
        found = next((i for i, t in enumerate(lines) if f'"{section}"' in t), None)
        if found is None:
            return 1
        start = found
    for i in range(start, len(lines)):
        if f'"{key}"' in lines[i]:
            return i + 1
    return start + 1


def _first_string(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for v in value.values():
            found = _first_string(v)
            if found:
                return found
    return None


def _item(path, line, kind, name, trigger, target, rule, snippet):
    return {"path": path, "line": line, "end_line": line, "kind": kind, "name": name, "trigger": trigger, "target": target,
            "rule": rule, "snippet": snippet}


def package_entries(project: dict, read) -> list:
    """Bins, scripts, the prisma seed and main/module/exports of every member package of `project`."""
    out = []
    for folder in project["members"]:
        path = _join(folder, "package.json")
        manifest = js_project.read_json(read, path)
        if manifest is None:
            continue
        lines = (read(path) or "").splitlines()
        pkg = manifest.get("name") if isinstance(manifest.get("name"), str) else (posixpath.basename(folder) or "package")

        bins = manifest.get("bin")
        if isinstance(bins, str):
            bins = {pkg: bins}
        for name, target in (bins.items() if isinstance(bins, dict) else []):
            if isinstance(target, str):
                line = _line_of(lines, "bin", name)
                out.append(_item(path, line, "package-bin", name, f"the `{name}` command", target, "js.package-bin", f"{name} = {target}"))

        scripts = [(f"{pkg} {k}", k, v, _line_of(lines, "scripts", k)) for k, v in (manifest.get("scripts") or {}).items() if isinstance(v, str)]
        seed = (manifest.get("prisma") or {}).get("seed") if isinstance(manifest.get("prisma"), dict) else None
        if isinstance(seed, str):
            scripts.append(("prisma seed", "prisma seed", seed, _line_of(lines, "prisma", "seed")))
        for name, script, command, line in scripts:
            out.append(_item(path, line, "package-script", name, f"running `{script}` with the package manager", command,
                             "js.package-script", f"{script}: {command}"))

        mains = [(k, manifest.get(k)) for k in ("main", "module")]
        exports = manifest.get("exports")
        mains.append(("exports", exports.get(".") if isinstance(exports, dict) and "." in exports else
                      (None if isinstance(exports, dict) and any(str(k).startswith(".") for k in exports) else exports)))
        for key, value in mains:
            target = _first_string(value)
            if target:
                out.append(_item(path, _line_of(lines, None, key), "package-main", target, "when another program imports or runs this package",
                                 target, "js.package-main", f"{key}: {target}"))
    return out


def nx_targets(tree, read) -> list:
    out = []
    for path in sorted(p for p in tree if posixpath.basename(p) == "project.json" and gather.noise_reason(p) is None):
        manifest = js_project.read_json(read, path)
        targets = manifest.get("targets") if manifest else None
        if not isinstance(targets, dict):
            continue
        folder = posixpath.dirname(path)
        project = manifest.get("name") if isinstance(manifest.get("name"), str) else (posixpath.basename(folder) or "project")
        lines = (read(path) or "").splitlines()
        for target in sorted(targets):
            spec = targets[target] if isinstance(targets[target], dict) else {}
            options = spec.get("options") if isinstance(spec.get("options"), dict) else {}
            command = options.get("command") if isinstance(options.get("command"), str) else spec.get("executor", "")
            out.append(_item(path, _line_of(lines, "targets", target), "nx-target", f"{project}:{target}", f"running `nx {target}`",
                             command, "js.nx-target", f"nx {target}"))
    return out


def _route(folders: list, stem: str | None) -> str:
    parts = [f for f in folders if not (f.startswith("(") and f.endswith(")"))] + ([stem] if stem else [])
    return "/" + "/".join(parts)


def next_routes(files, project: dict) -> list:
    """Routes from the file layout of one Next.js package (`project["dir"]`): the app router and the pages router."""
    prefix = project["dir"] + "/" if project["dir"] else ""
    out = []
    for f in sorted(files):
        if not f.startswith(prefix) or not f.endswith(CODE_EXT) or f.endswith(".d.ts"):
            continue
        if gather.noise_reason(f) or gather.TEST_RE.search(f):
            continue
        rel = f[len(prefix):]
        base, stem = rel.split("/"), posixpath.splitext(posixpath.basename(rel))[0]
        for root, router in (("src/app/", "app"), ("app/", "app"), ("src/pages/", "pages"), ("pages/", "pages")):
            if not rel.startswith(root):
                continue
            folders = rel[len(root):].split("/")[:-1]
            if any(seg.startswith(("_", "@")) for seg in folders):
                break
            if router == "app":
                if stem == "page":
                    name = _route(folders, None)
                elif stem == "route":
                    name = "API " + _route(folders, None)
                else:
                    break
            else:
                if stem in NEXT_SPECIAL:
                    break
                name = _route(folders, None if stem == "index" else stem)
                if folders[:1] == ["api"]:
                    name = "API " + name
            out.append(_item(f, 1, "http-route", name, f"a web request to `{name}`", f, "js.next-route", name))
            break
    return out
