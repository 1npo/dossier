"""Pure reducers from the JavaScript tools' JSON to adapter items (plan 010, D4, D12). Nothing here runs a process."""
from __future__ import annotations

import posixpath

import graphs

JS_EXT = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")


def _join(folder: str, path: str) -> str:
    return posixpath.join(folder, path) if folder else path


def _stem(path: str) -> str:
    return posixpath.splitext(posixpath.basename(path))[0]


def module_name(path: str, siblings) -> str:
    """The path without its last extension, or the full path when another file in the folder has the same stem."""
    base = posixpath.splitext(path)[0]
    clash = any(s != path and posixpath.splitext(s)[0] == base for s in siblings)
    return path if clash else base


def short_name(path: str) -> str:
    """The file's stem, or the parent folder's name for an `index` file."""
    stem = _stem(path)
    parent = posixpath.basename(posixpath.dirname(path))
    return parent if stem == "index" and parent else stem


def _is_code(path: str, test_re) -> bool:
    return not path.endswith(".d.ts") and not path.endswith((".d.mts", ".d.cts")) and not test_re.search(path)


def _line_index(imports) -> dict:
    index: dict = {}
    for i in imports or []:
        index.setdefault((i["path"], i["specifier"]), set()).add(i["line"])
    return index


def graph_items(cruise: dict, project: dict, tree, imports, test_re) -> tuple[list, list]:
    """Module, import and cycle items for one project, and the edges that start in test files as (from path, to path) pairs."""
    folder = project.get("dir") or ""
    files = [f for f in project["files"] if f in tree and _is_code(f, test_re)]
    names = {f: module_name(f, files) for f in files}
    items = [{"kind": "module", "path": f, "module": names[f], "short": short_name(f), "package": None, "is_package": False,
              "language": "js", "project": folder} for f in sorted(files)]
    lines = _line_index(imports)
    merged: dict = {}
    test_edges = set()
    for mod in cruise.get("modules", []):
        src = _join(folder, mod["source"])
        for dep in mod.get("dependencies", []):
            dst = _join(folder, dep.get("resolved") or "")
            if not dep.get("resolved") or dst not in tree or "node_modules/" in dst:
                continue
            if test_re.search(src) and dst in names:
                test_edges.add((src, dst))
                continue
            if src not in names or dst not in names or src == dst:
                continue
            e = merged.setdefault((src, dst), {"lines": set(), "type_only": True, "dynamic": True})
            e["lines"] |= lines.get((src, dep["module"]), set())
            e["type_only"] &= "type-only" in dep.get("dependencyTypes", [])
            e["dynamic"] &= bool(dep.get("dynamic"))
    for (src, dst), e in sorted(merged.items()):
        items.append({"kind": "import", "path": src, "paths": [dst], "from": names[src], "to": names[dst], "lines": sorted(e["lines"]),
                      "via": "dependency-cruiser", "type_only": e["type_only"], "dynamic": e["dynamic"]})
    items += cycle_items(items, names)
    return items, sorted(test_edges)


def cycle_items(items: list, names: dict | None = None) -> list:
    """Cycles over the imports that exist at run time (a type-only import is not one)."""
    by_module = {i["module"]: i["path"] for i in items if i["kind"] == "module"}
    pairs = [(i["from"], i["to"]) for i in items if i["kind"] == "import" and not i["type_only"]]
    out = []
    for members in graphs.cycles(pairs):
        files = [by_module[m] for m in members if m in by_module]
        if files:
            out.append({"kind": "cycle", "path": files[0], "paths": files, "modules": members})
    return out


def contract_items(violations: list, rule_names: list, config_path: str, names: dict | None = None, lines: dict | None = None) -> list:
    """One `contract` item per rule: `broken` with its violations, or `kept`. Rules seen only in violations are added as broken."""
    names, lines = names or {}, lines or {}
    by_rule: dict = {}
    for v in violations:
        by_rule.setdefault(v["rule"]["name"], []).append(v)
    out = []
    for name in sorted(set(rule_names) | set(by_rule)):
        found = by_rule.get(name, [])
        out.append({"kind": "contract", "path": config_path, "contract": name, "type": "dependency-cruiser",
                    "status": "broken" if found else "kept",
                    "violations": [{"from": names.get(v["from"], v["from"]), "to": names.get(v["to"], v["to"]), "path": v["from"],
                                    "line": lines.get((v["from"], v["to"]))} for v in found], "reason": None})
    return out


def prefix_facts(facts: dict, folder: str) -> dict:
    """Make the paths in a `ts_facts` response relative to the checkout instead of the project folder."""
    if not folder:
        return facts
    def fix(p):
        return _join(folder, p) if p else p
    out = dict(facts)
    for key in ("imports", "exports", "types", "components", "routes"):
        out[key] = [{**row, "path": fix(row["path"])} for row in facts.get(key, [])]
    for row in out["components"]:
        row["renders"] = [{**r, "path": fix(r["path"])} for r in row["renders"]]
    for row in out["routes"]:
        row["file"] = fix(row.get("file"))
    return out
