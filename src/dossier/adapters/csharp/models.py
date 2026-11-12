"""Data entities and migrations for C#, from declarations and a little source text (plan 011, D13). Pure.

An entity is only a type that a data store holds: an EF Core entity type, an owned type, a Dapper row type or a `[Table]` class,
plus the enums those use. DTOs, records, view models, options classes and message types are left out.
"""
from __future__ import annotations

import re

DBSET_RE = re.compile(r"^(?:[\w.]+\.)?DbSet<\s*([\w.]+)\s*>$")
ENTITY_CALL_RE = re.compile(r"\.Entity<\s*([\w.]+)\s*>\s*\(")
OWNS_RE = re.compile(r"\.Owns(?:One|Many)<\s*([\w.]+)\s*>")
DAPPER_RE = re.compile(r"\.(?:Query|QueryFirst|QueryFirstOrDefault|QuerySingle|QuerySingleOrDefault)(?:Async)?<\s*([\w.]+)\s*>\s*\(")
KIND_ORDER = ("ef-entity", "ef-owned", "dapper-row", "table-class")
CONFIG_BASE_RE = re.compile(r"^(?:[\w.]+\.)?IEntityTypeConfiguration<\s*([\w.]+)\s*>$")
COLLECTION_RE = re.compile(r"^(?:ICollection|IList|List|IEnumerable|HashSet|ISet|IReadOnlyCollection|IReadOnlyList)<\s*([\w.]+)\s*>$")
DB_CONTEXT_RE = re.compile(r"^(?:[\w.]+\.)?(?:Identity)?DbContext(?:<.*>)?$")


def _last(name: str) -> str:
    return re.sub(r"<.*$", "", name).rsplit(".", 1)[-1]


def _types(decls: dict) -> dict:
    """{simple name: [(path, type)]} for every declared type, in path and line order."""
    out: dict = {}
    for path in sorted(decls):
        for t in decls[path]["types"]:
            out.setdefault(t["name"], []).append((path, t))
    return out


def _visible(decls: dict, path: str) -> set:
    d = decls[path]
    names = {""}
    for ns in (n["name"] for n in d["namespaces"]):
        parts = ns.split(".")
        names |= {".".join(parts[:i]) for i in range(1, len(parts) + 1)}
    names |= {u["name"] for u in d["usings"] if not u["alias"]}
    names |= {u["name"] for f in decls.values() for u in f["usings"] if u["global"] and not u["alias"]}
    return names


def _resolve(name: str, from_path: str, decls: dict, types: dict):
    """The (path, type) parts of the type `name` that `from_path` can see, or None when none or two different types match."""
    simple = _last(name)
    found = types.get(simple, [])
    if not found:
        return None
    if "." in name:
        namespace = name.rsplit(".", 1)[0]
        found = [(p, t) for p, t in found if t["namespace"] == namespace or t["namespace"].endswith("." + namespace)] or found
    elif len(found) > 1:
        seen = _visible(decls, from_path)
        found = [(p, t) for p, t in found if t["namespace"] in seen]
    if len({t["namespace"] for _, t in found}) != 1:
        return None
    return found


def _db_contexts(decls: dict) -> set:
    """Names of classes that are, or derive from, a DbContext."""
    classes = {t["name"]: t for d in decls.values() for t in d["types"] if t["kind"] == "class"}
    known = {n for n, t in classes.items() if any(DB_CONTEXT_RE.match(b) for b in t["bases"])}
    grew = True
    while grew:
        grew = False
        for n, t in classes.items():
            if n not in known and any(_last(b) in known for b in t["bases"]):
                known.add(n)
                grew = True
    return known


def _field_type(text: str) -> str:
    return (text or "").replace("?", "").strip()


def _fields(parts: list, decls: dict, types: dict, seen: set | None = None) -> list:
    """Public readable properties of the type (all parts), then those of its bases declared in the repository."""
    seen = seen or set()
    out = []
    for path, t in parts:
        for m in t["members"]:
            if m["kind"] == "property" and "public" in m["modifiers"] and not m["static"] and m.get("get", True):
                out.append((m, t["name"]))
        for b in t["bases"]:
            base = _resolve(b, path, decls, types)
            key = _last(b)
            if base and key not in seen and key != t["name"] and not b.startswith("I"):
                out += _fields(base, decls, types, seen | {t["name"], key})
    return out


def _element(type_text: str) -> tuple:
    """(element type, many) of a property type: collections give their element type."""
    clean = _field_type(type_text)
    found = COLLECTION_RE.match(clean)
    return (found.group(1), True) if found else (clean, False)


def _entity_item(kind: str, parts: list, decls: dict, types: dict, names: set, enums: set) -> dict:
    path, t = parts[0]
    fields, relations = [], []
    for m, owner in _fields(parts, decls, types):
        elem, many = _element(m["type"] or "")
        elem = _last(elem)
        target = elem if elem in names or elem in enums else None
        is_key = any(a["name"] == "Key" for a in m["attributes"]) or m["name"] in ("Id", f"{t['name']}Id")
        fields.append({"name": m["name"], "type": _field_type(m["type"]), "line": m["line"], "ref": target, "pk": is_key, "many": many})
        if target and target in names:
            relations.append({"field": m["name"], "to": target, "kind": "ef"})
    return {"path": path, "line": t["line"], "end_line": t["end_line"], "name": t["name"], "kind": kind, "rule": f"cs.{kind}",
            "snippet": f"{t['kind']} {t['name']}", "bases": t["bases"], "fields": fields, "relations": relations}


def _enum_item(parts: list) -> dict:
    path, t = parts[0]
    return {"path": path, "line": t["line"], "end_line": t["end_line"], "name": t["name"], "kind": "cs-enum", "rule": "cs.cs-enum", "snippet": f"enum {t['name']}",
            "bases": t["bases"], "fields": [{"name": m["name"], "type": None, "line": m["line"], "ref": None} for m in t["members"] if m["kind"] == "enum-member"],
            "relations": []}


def _migrations(decls: dict) -> list:
    out = []
    for path, d in sorted(decls.items()):
        for t in d["types"]:
            bases = {_last(b) for b in t["bases"]}
            marks = [a for a in t["attributes"] if a["name"] == "Migration"]
            if "Migration" in bases and marks:
                strings = re.findall(r'"([^"]*)"', marks[0]["args"])
                out.append({"path": path, "line": t["line"], "kind": "migration", "tool": "ef-core", "name": strings[0] if strings else t["name"], "rule": "cs.migration"})
            elif "ModelSnapshot" in bases:
                out.append({"path": path, "line": t["line"], "kind": "migration", "tool": "ef-core", "name": t["name"], "snapshot": True, "rule": "cs.migration"})
    return out


def model_items(decls: dict, projects: dict, read=None, generated=frozenset(), tests=frozenset()) -> list:
    """Entity items (`ef-entity`, `ef-owned`, `dapper-row`, `table-class`, `cs-enum`) and `migration` items.

    `read(path)` gives a file's text, for the `Entity<T>()`, `OwnsOne<T>()` and Dapper `Query<T>()` calls that declarations do not hold."""
    del projects
    read = read or (lambda p: None)
    types = _types(decls)
    contexts = _db_contexts(decls)
    found: dict = {}  # (name, namespace) -> (kind, parts); one kind per type, the first in KIND_ORDER wins

    def add(kind: str, name: str, from_path: str) -> None:
        parts = _resolve(name, from_path, decls, types)
        if not parts or parts[0][0] in generated or parts[0][1]["kind"] not in ("class", "record", "struct"):
            return
        key = parts[0][1]["name"], parts[0][1]["namespace"]
        if key not in found or KIND_ORDER.index(kind) < KIND_ORDER.index(found[key][0]):
            found[key] = (kind, parts)

    for path in sorted(decls):
        for t in decls[path]["types"]:
            for b in t["bases"]:
                cfg = CONFIG_BASE_RE.match(b)
                if cfg:
                    add("ef-entity", cfg.group(1), path)
            if t["name"] in contexts:
                for m in t["members"]:
                    dbset = DBSET_RE.match(m["type"] or "") if m["kind"] == "property" else None
                    if dbset:
                        add("ef-entity", dbset.group(1), path)
            if any(a["name"] == "Owned" for a in t["attributes"]):
                add("ef-owned", t["name"], path)
            if any(a["name"] == "Table" for a in t["attributes"]):
                add("table-class", t["name"], path)
        if path in tests:
            continue
        text = read(path) or ""
        if any(c in contexts for c in (t["name"] for t in decls[path]["types"])) or "Entity<" in text:
            for m in ENTITY_CALL_RE.finditer(text):
                add("ef-entity", m.group(1), path)
        for m in OWNS_RE.finditer(text):
            add("ef-owned", m.group(1), path)
        for m in DAPPER_RE.finditer(text):
            add("dapper-row", m.group(1), path)
    names = {k[0] for k in found}
    enums = _enums_used([parts for _, parts in found.values()], decls, types)
    items = [_entity_item(kind, parts, decls, types, names, {n for n, _ in enums}) for kind, parts in found.values()]
    items += [_enum_item(parts) for _, parts in enums]
    return sorted(items, key=lambda i: (i["path"], i["line"], i["name"])) + _migrations(decls)


def _enums_used(entities: list, decls: dict, types: dict) -> list:
    """[(name, parts)] for each enum declared in the repository that a field of an entity uses."""
    out: dict = {}
    for parts in entities:
        for m, _ in _fields(parts, decls, types):
            elem = _last(_element(m["type"] or "")[0])
            hit = [(p, t) for p, t in types.get(elem, []) if t["kind"] == "enum"]
            if hit and len({t["namespace"] for _, t in hit}) == 1:
                out.setdefault((hit[0][1]["name"], hit[0][1]["namespace"]), hit)
    return [(k[0], v) for k, v in sorted(out.items())]
