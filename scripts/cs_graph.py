"""The C# graph: module items, type-use edges between files, and namespace cycles (plan 011, D8). Pure.

C# files do not import each other: `using` names a namespace. A file A is linked to a file B when A uses a type that B declares and
A can see it (its namespaces, its `using` lines, its project and the projects it references). This is read from the text, so uses
through extension methods, `var`, reflection or dependency injection are not linked.
"""
from __future__ import annotations

import graphs


def module_name(path: str) -> str:
    return path[:-3] if path.endswith(".cs") else path


def module_items(projects: dict, decls: dict, complexity: dict, generated: set, test_files=frozenset()) -> list:
    """One `module` item per source file (test files are not modules)."""
    owner = {f: p["path"] for p in projects["projects"] if "language" not in p for f in p["files"]}
    items = []
    for path in sorted(decls):
        if path in test_files:
            continue
        gen = path in generated
        items.append({"kind": "module", "path": path, "module": module_name(path), "short": path.rsplit("/", 1)[-1][:-3],
                      "namespaces": [n["name"] for n in decls[path]["namespaces"]], "project": owner.get(path), "language": "csharp",
                      "generated": gen, "complexity": 0 if gen else complexity.get(path, 0)})
    return items


def _parents(namespace: str) -> list:
    """The namespace and each enclosing one, innermost first, without the global namespace."""
    parts = namespace.split(".") if namespace else []
    return [".".join(parts[:i]) for i in range(len(parts), 0, -1)]


def _reachable(projects: dict) -> dict:
    """{csproj path: set of csproj paths it can use, itself included}."""
    refs = {p["path"]: p["references"] for p in projects["projects"] if "language" not in p}
    out = {}
    for start in refs:
        seen, todo = set(), [start]
        while todo:
            p = todo.pop()
            if p in seen:
                continue
            seen.add(p)
            todo.extend(refs.get(p, ()))
        out[start] = seen
    return out


def _index(decls: dict, skip) -> dict:
    """{simple name: {(namespace, name): [files]}} for every declared type outside `skip`."""
    index: dict = {}
    for path, d in decls.items():
        if path in skip:
            continue
        for t in d["types"]:
            ns = t["namespace"]
            entry = index.setdefault(t["name"], {}).setdefault((ns, t["name"]), [])
            if (path, t["partial"]) not in entry:
                entry.append((path, t["partial"]))
    return index


def _qualified_hits(d: dict, index: dict) -> set:
    """Names written with their namespace (`Shop.Core.Order`) that match a declaration exactly: {(namespace, name)}."""
    hits = set()
    for q in d["qualified"]:
        parts = q.split(".")
        for k in range(1, len(parts)):
            key = (".".join(parts[:k]), parts[k])
            if key in index.get(parts[k], {}):
                hits.add(key)
    return hits


def type_uses(decls: dict, projects: dict, test_files=frozenset(), generated=frozenset()) -> tuple:
    """(import items, test edges, ambiguous count).

    A name that two different types could satisfy gives no edge and adds one to the count (per file and name)."""
    owner = {f: p["path"] for p in projects["projects"] if "language" not in p for f in p["files"]}
    reach = _reachable(projects)
    index = _index(decls, set(test_files))
    global_usings: dict = {}
    for path, d in decls.items():
        for u in d["usings"]:
            if u["global"] and not u["alias"]:
                global_usings.setdefault(owner.get(path), set()).add(u["name"])
    edges: dict = {}
    ambiguous = 0
    for a in sorted(decls):
        d = decls[a]
        if not d["types"] and not d["idents"]:
            continue
        project = owner.get(a)
        usable = reach.get(project, {project})
        own = {t["name"] for t in d["types"]}
        enclosing = [n for ns in (x["name"] for x in d["namespaces"]) for n in _parents(ns)]
        used_ns = {u["name"] for u in d["usings"] if not u["alias"]} | global_usings.get(project, set()) | {""}
        aliases = {u["alias"]: u["name"] for u in d["usings"] if u["alias"]}
        names = {n: lines for n, lines in d["idents"].items()}
        for alias, target in aliases.items():
            if alias in names:
                names.setdefault(target.rsplit(".", 1)[-1], names[alias])
        qualified = _qualified_hits(d, index)
        for name, lines in sorted(names.items()):
            if name in own or name not in index:
                continue
            kinds = {k: [(f, p) for f, p in files if owner.get(f) in usable]
                     for k, files in index[name].items()}
            kinds = {k: v for k, v in kinds.items() if v}
            chosen = [k for k in kinds if k[0] in enclosing]
            if chosen:
                chosen.sort(key=lambda k: -len(k[0]))
                chosen = [k for k in chosen if len(k[0]) == len(chosen[0][0])]
            else:
                chosen = [k for k in kinds if k[0] in used_ns or k in qualified]
            if not chosen:
                continue
            if len(chosen) > 1 or any(len(kinds[k]) > 1 and not all(p for _, p in kinds[k]) for k in chosen):
                ambiguous += 1
                continue
            for f, _ in kinds[chosen[0]]:
                if f != a:
                    entry = edges.setdefault((a, f), {"lines": [], "names": set()})
                    entry["lines"].append(min(lines))
                    entry["names"].add(name)
    imports, test_edges = [], []
    for (a, b), entry in sorted(edges.items()):
        if a in test_files:
            test_edges.append((a, b))
        elif a not in generated:
            imports.append({"kind": "import", "path": a, "paths": [b], "from": module_name(a), "to": module_name(b), "lines": [min(entry["lines"])],
                            "via": "type-use", "type_only": False, "dynamic": False, "names": sorted(entry["names"])})
    return imports, test_edges, ambiguous


def namespace_cycles(imports: list, decls: dict, projects: dict) -> list:
    """`cycle` items between namespaces of one project. Files that use each other inside one namespace are normal and give none."""
    owner = {f: p["path"] for p in projects["projects"] if "language" not in p for f in p["files"]}

    def ns_of(path):
        names = [n["name"] for n in decls.get(path, {}).get("namespaces", [])]
        return names[0] if names else ""
    by_project: dict = {}
    for i in imports:
        a, b = i["path"], i["paths"][0]
        if owner.get(a) != owner.get(b) or ns_of(a) == ns_of(b):
            continue
        by_project.setdefault(owner.get(a), []).append((ns_of(a), ns_of(b), a, b))
    items = []
    for project, rows in sorted(by_project.items(), key=lambda kv: str(kv[0])):
        for members in graphs.cycles([(x, y) for x, y, _, _ in rows]):
            files = sorted({f for x, y, a, b in rows if x in members and y in members for f in (a, b)})
            items.append({"kind": "cycle", "path": files[0], "paths": files, "modules": members, "level": "namespace", "project": project})
    return items
