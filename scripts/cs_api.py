"""What a C# project offers to other code (plan 011, D15): the per-file `public` flag and the real public API.

Pure: no file access, no process. The flag says a name can be reached from outside its own file. The real public API is the
smaller set another assembly (a NuGet consumer) can use: the public names of packable library projects.
"""
from __future__ import annotations

MEMBER_KINDS = {"enum-member": "enum member"}


def _own_public(decl: dict, container: dict | None) -> bool:
    """Whether a declaration's own accessibility reaches outside its container (D15), ignoring the container itself."""
    mods = set(decl.get("modifiers") or ())
    if "file" in mods:
        return False
    if "public" in mods:
        return True
    if "protected" in mods:
        return "private" not in mods
    if mods & {"internal", "private"}:
        return False
    # No modifier: an interface member and a nested type of an interface are public, an enum member takes its enum, the rest is private or internal.
    return decl.get("kind") == "enum-member" or (container is not None and container.get("kind") == "interface")


def is_public(decl: dict, outers: list, partial_parts: list) -> bool:
    """D15. `outers` are the enclosing types, outermost first. `partial_parts` are every part of the nearest type (the declaration
    itself when it is a type, else the last outer), or empty; the type is public when any part says so."""
    is_type = "members" in decl
    for i, outer in enumerate(outers[:-1] if not is_type else outers):
        if not _own_public(outer, outers[i - 1] if i else None):
            return False
    container = outers[-1] if outers else None
    if is_type:
        parts = partial_parts or [decl]
        return any(_own_public(p, container) for p in parts)
    if container is not None:
        parts = partial_parts or [container]
        grand = outers[-2] if len(outers) > 1 else None
        if not any(_own_public(p, grand) for p in parts):
            return False
    return _own_public(decl, container)


def _chain(t: dict, by_name: dict) -> list:
    """The enclosing types of `t` in the same file, outermost first."""
    chain, seen, name = [], {t["name"]}, t.get("outer")
    while name and name not in seen and name in by_name:
        seen.add(name)
        chain.insert(0, by_name[name])
        name = by_name[name].get("outer")
    return chain


def _parts(files: dict) -> dict:
    """Every part of each partial type, by (namespace, dotted name)."""
    parts: dict = {}
    for decls in files.values():
        by_name = {t["name"]: t for t in decls["types"]}
        for t in decls["types"]:
            if t.get("partial"):
                parts.setdefault(_key(t, by_name), []).append(t)
    return parts


def _key(t: dict, by_name: dict) -> tuple:
    names = [o["name"] for o in _chain(t, by_name)] + [t["name"]]
    return t.get("namespace"), ".".join(names)


def line_flags(decls: dict, parts: dict | None = None) -> list:
    """[(name, line, end_line, public)] for every type and member of one file, for the `public` flag on `def` items."""
    by_name = {t["name"]: t for t in decls["types"]}
    parts = parts if parts is not None else _parts({"": decls})
    out = []
    for t in decls["types"]:
        outers = _chain(t, by_name)
        same = parts.get(_key(t, by_name), [])
        out.append((t["name"], t["line"], t["end_line"], is_public(t, outers, same)))
        for m in t["members"]:
            out.append((m["name"], m["line"], m["end_line"], is_public(m, outers + [t], same)))
    return out


def _audience(decl: dict) -> str:
    names = {a["name"]: a.get("args", "") for a in decl.get("attributes", [])}
    text = "packable"
    if "EditorBrowsable" in names and "Never" in names["EditorBrowsable"]:
        text += ", hidden from editors"
    if "Obsolete" in names:
        text += ", obsolete"
    return text


def _reachable(member: dict, t: dict) -> bool:
    """`protected` cannot be reached from a sealed or static class."""
    mods = set(member.get("modifiers") or ())
    if "public" in mods or not (mods & {"protected"}):
        return True
    return not (set(t.get("modifiers") or ()) & {"sealed", "static"})


def _member_rows(t: dict) -> list:
    """(name, symbol_kind, line, decl) per name of a type's members, overloads joined."""
    groups: dict = {}
    for m in t["members"]:
        groups.setdefault((m["name"], m["kind"]), []).append(m)
    rows = []
    for (name, kind), ms in groups.items():
        word = MEMBER_KINDS.get(kind, kind)
        if kind == "method" and any(p.get("this") for m in ms for p in m["params"][:1]):
            word = "extension method"
        if len(ms) > 1 and kind in ("method", "constructor"):
            word += f" ({len(ms)} overloads)"
        rows.append((name, word, min(m["line"] for m in ms), ms))
    for p in t.get("params", ()):  # a record's positional parameters are properties
        rows.append((p["name"], "property", t["line"], [{"modifiers": ["public"], "kind": "property", "attributes": []}]))
    return rows


def _project_rows(p: dict, decls: dict, generated: set, parts: dict) -> list:
    package = p.get("package_id") or p.get("assembly") or p["name"]
    out, seen = [], set()
    for path in sorted(p["files"]):
        if path in generated or path not in decls:
            continue
        by_name = {t["name"]: t for t in decls[path]["types"]}
        for t in decls[path]["types"]:
            outers = _chain(t, by_name)
            same = parts.get(_key(t, by_name), [])
            dotted = ".".join([o["name"] for o in outers] + [t["name"]])
            if not is_public(t, outers, same):
                continue
            base = {"kind": "public-api", "package": package, "subpath": t.get("namespace") or "", "audience": _audience(t)}
            if (dotted, "") not in seen:
                seen.add((dotted, ""))
                out.append({**base, "path": path, "line": t["line"], "name": dotted, "symbol_kind": t["kind"]})
            for name, word, line, ms in _member_rows(t):
                key = (dotted, name)
                if key in seen or not any(is_public(m, outers + [t], same) and _reachable(m, t) for m in ms):
                    continue
                seen.add(key)
                out.append({**base, "path": path, "line": line, "name": f"{dotted}.{name}", "symbol_kind": word, "audience": _audience(ms[0])})
    return out


def items(projects: list, decls: dict, generated) -> tuple:
    """(`public-api` symbols, `cs-note` items, [{"project", "friend"}]) for the packable projects."""
    generated = set(generated)
    parts = _parts({f: d for f, d in decls.items() if f not in generated})
    symbols, notes, friends = [], [], []
    for p in projects:
        if "language" in p or not p.get("packable") or p.get("test"):
            continue
        symbols += _project_rows(p, decls, generated, parts)
        if any(f not in decls and f not in generated for f in p["files"]):
            notes.append({"kind": "cs-note", "path": p["path"], "note": "api", "name": p["name"]})
        friends += [{"project": p["name"], "friend": f} for f in p.get("friends", [])]
    return sorted(symbols, key=lambda s: (s["package"], s["subpath"], s["name"])), notes, friends
