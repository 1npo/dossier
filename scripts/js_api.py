"""The real public API of a JavaScript package (plan 010, D17): what another package can import, as Node's rules say.

`entries` maps a package.json's `exports`, `main`, `module` and `types` to tracked source files. The TypeScript script then lists the
names each entry file exports, and `items` turns those into `public-api` symbols. This is separate from the `public` flag of a symbol,
which only says a name is exported from its own file (S9). Pure: no file access, no process.
"""
from __future__ import annotations

import json
import posixpath
import re

CODE = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
SOURCE_EXT = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
DECL = re.compile(r"\.d\.(m|c)?ts$")


def read_tsconfig(read, path: str) -> dict | None:
    """The `compilerOptions` of a tsconfig, tolerating comments and trailing commas. `extends` is not followed."""
    text = read(path)
    if text is None:
        return None
    text = re.sub(r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/', lambda m: m.group(1) or "", text, flags=re.S)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    try:
        data = json.loads(text)
    except ValueError:
        return None
    options = data.get("compilerOptions") if isinstance(data, dict) else None
    return options if isinstance(options, dict) else {}


def _norm(folder: str, target: str) -> str:
    return posixpath.normpath(posixpath.join(folder, target)) if folder else posixpath.normpath(target)


def _variants(path: str) -> list:
    """Source file names a built or declaration file may come from."""
    base = DECL.sub("", path) if DECL.search(path) else posixpath.splitext(path)[0]
    return [base + e for e in (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx")]


def _first_tracked(candidates: list, tracked: set) -> str | None:
    for c in candidates:
        for v in [c] + _variants(c):
            if v in tracked and not DECL.search(v):
                return v
    return None


def _map_target(target: str, subpath: str, name: str, folder: str, tracked: set, options: dict) -> str | None:
    """The tracked source file that a manifest target stands for, or None."""
    full = _norm(folder, target)
    if full in tracked and not DECL.search(full):
        return full
    spec = name + subpath[1:]
    for key, values in (options.get("paths") or {}).items():
        star = key.endswith("*")
        if (star and spec.startswith(key[:-1])) or key == spec:
            rest = spec[len(key) - 1:] if star else ""
            base = options.get("baseUrl") or "."
            hit = _first_tracked([_norm(folder, posixpath.join(base, v.replace("*", rest))) for v in values], tracked)
            if hit:
                return hit
    out_dir, root_dir = options.get("outDir"), options.get("rootDir")
    if out_dir is not None and root_dir is not None:
        prefix = _norm(folder, out_dir) + "/"
        if full.startswith(prefix):
            hit = _first_tracked([_norm(folder, root_dir) + "/" + full[len(prefix):]], tracked)
            if hit:
                return hit
    rel = posixpath.relpath(full, folder or ".")
    parts = rel.split("/")
    tries = [_norm(folder, "src/" + "/".join(parts[1:]))] if len(parts) > 1 else []
    tries.append(_norm(folder, "src/" + parts[-1]))
    return _first_tracked(tries, tracked)


def _walk(value, found: list) -> None:
    """Every target string in a conditions value, in order, depth first."""
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, list):
        for v in value:
            _walk(v, found)
    elif isinstance(value, dict):
        for v in value.values():
            _walk(v, found)


def _is_code(target: str) -> bool:
    return target.endswith(CODE)


def _expand(pattern: str, key: str, name: str, folder: str, tracked: set, options: dict) -> list:
    """[(subpath, file)] for a wildcard mapping, over the source files that the target pattern can come from."""
    results = []
    out_dir, root_dir = options.get("outDir"), options.get("rootDir")
    regex = re.compile("^" + re.escape(_norm(folder, pattern)).replace(r"\*", "(.+)") + "$")
    prefix = folder + "/" if folder else ""
    for f in sorted(tracked):
        if not f.startswith(prefix) or DECL.search(f) or not f.endswith(SOURCE_EXT):
            continue
        shapes = [f]
        if out_dir is not None and root_dir is not None and f.startswith(_norm(folder, root_dir) + "/"):
            built = _norm(folder, out_dir) + "/" + f[len(_norm(folder, root_dir)) + 1:]
            shapes += [posixpath.splitext(built)[0] + e for e in (".js", ".mjs", ".cjs", ".d.ts")]
        for shape in shapes:
            m = regex.match(shape)
            if m:
                results.append((key.replace("*", m.group(1)), f))
                break
    return results


def entries(project: dict, tracked, tsconfig: dict | None) -> list:
    """Rows {package, subpath, file, resolved, audience} for one package. `project` is {"dir", "manifest"}."""
    manifest, folder = project["manifest"], project["dir"]
    tracked, options = set(tracked), tsconfig or {}
    name = manifest.get("name") if isinstance(manifest.get("name"), str) else folder or "."
    audience = "marked private" if manifest.get("private") is True else "not marked private"
    rows = []

    def row(subpath, file):
        rows.append({"package": name, "subpath": subpath, "file": file, "resolved": file is not None, "audience": audience})

    exports = manifest.get("exports")
    if exports is not None:
        table = exports if isinstance(exports, dict) and any(k.startswith(".") for k in exports) else {".": exports}
        for key, value in table.items():
            if not key.startswith(".") or value is None:
                continue
            targets: list = []
            _walk(value, targets)
            targets = [t for t in targets if _is_code(t)]
            if not targets:
                continue
            if "*" in key:
                for target in targets:
                    found = _expand(target, key, name, folder, tracked, options)
                    if found:
                        for sub, f in found:
                            row(sub, f)
                        break
                else:
                    row(key, None)
                continue
            row(key, next((f for f in (_map_target(t, key, name, folder, tracked, options) for t in targets) if f), None))
        return sorted(rows, key=lambda r: (r["subpath"], r["file"] or ""))
    present = [manifest[k] for k in ("main", "module", "types") if isinstance(manifest.get(k), str)]
    if not present:
        return []
    row(".", next((f for f in (_map_target(t, ".", name, folder, tracked, options) for t in present) if f), None))
    return rows


def items(entry_rows: list, api: list, unresolved: list) -> tuple:
    """(`public-api` symbols, `js-note` items for entries and names that could not be worked out)."""
    by_entry = {(e["file"], e["subpath"]): e for e in entry_rows if e["file"]}
    symbols = []
    for a in api:
        e = by_entry.get((a["entry"], a["subpath"]))
        if e is None:
            continue
        symbols.append({"kind": "public-api", "path": a["path"] or a["entry"], "line": a["line"], "name": a["name"], "symbol_kind": a["kind"],
                        "package": e["package"], "subpath": a["subpath"], "audience": e["audience"], "external": a.get("external")})
    notes = [{"kind": "js-note", "path": e["file"] or "package.json", "note": "api", "name": f"{e['package']}|{e['subpath']}"} for e in entry_rows if not e["resolved"]]
    for u in unresolved:
        e = by_entry.get((u["entry"], u["subpath"]))
        if e is not None:
            notes.append({"kind": "js-note", "path": u["entry"], "note": "api", "name": f"{e['package']}|{e['subpath']}"})
    seen, unique = set(), []
    for n in notes:
        if (n["path"], n["name"]) not in seen:
            seen.add((n["path"], n["name"]))
            unique.append(n)
    return sorted(symbols, key=lambda s: (s["package"], s["subpath"], s["name"])), unique
