"""Pure reducers from the JavaScript tools' JSON to adapter items (plan 010, D4, D12). Nothing here runs a process."""
from __future__ import annotations

import posixpath
import re

import gather
import graphs
import scip_read

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
    out["api"] = [{**row, "entry": fix(row["entry"]), "path": fix(row["path"])} for row in facts.get("api", [])]
    out["api_unresolved"] = [{**row, "entry": fix(row["entry"])} for row in facts.get("api_unresolved", [])]
    return out


_DEAD = (("exports", "knip.exports", "unused export", "Exported, but nothing imports it."),
         ("types", "knip.types", "unused type", "Exported type that nothing imports."))


def dead_items(knip: dict, project: dict) -> list:
    """`dead` items from knip's JSON (one issue per file). Dependencies point at the project's package.json."""
    folder = project.get("dir") or ""
    manifest = _join(folder, "package.json")
    items = []

    def add(path, rule, kind, name, message, line=None):
        items.append({"path": path, "line": line, "end_line": line, "type": kind, "name": name, "message": message, "confidence": None,
                      "rule": rule, "snippet": name})
    for issue in knip.get("issues", []):
        path = _join(folder, issue["file"])
        for f in issue.get("files") or []:
            add(_join(folder, f["name"]), "knip.files", "unused file", f["name"], "No entry point or other file uses this file.")
        for key in ("dependencies", "devDependencies"):
            for d in issue.get(key) or []:
                add(manifest, "knip.dependencies", "unused dependency", d["name"], "Listed in package.json, but no file imports it.", d.get("line"))
        for key, rule, kind, message in _DEAD:
            for e in issue.get(key) or []:
                add(path, rule, kind, e["name"], message, e.get("line"))
    return items


def join_indexes(pairs: list) -> dict:
    """One decoded index from several: `pairs` are (project dir, decoded index), and each document path gets the project's folder."""
    documents = []
    for folder, index in pairs:
        for d in index["documents"]:
            documents.append({**d, "path": _join(folder, d["path"])})
    return {"documents": documents}


def _anonymous(symbol: str) -> str:
    """Drop the package name and version from a global symbol, so a digest does not change when package.json's version does."""
    if symbol.startswith("local "):
        return symbol
    parts = symbol.split(" ", 4)
    return " ".join([parts[0], parts[1], ".", ".", parts[4]]) if len(parts) == 5 else symbol


def _top_level(symbol: str) -> str | None:
    """The first name after the file in a symbol, `Order` for ``src/`types.ts`/Order#id.``; None for the file's own module symbol."""
    ds = scip_read.descriptors(symbol)
    last_dir = max((n for n, (_, suffix) in enumerate(ds) if suffix == "/"), default=-1)
    return ds[last_dir + 1][0] if last_dir >= 0 and last_dir + 1 < len(ds) else None


def finish_symbols(items: list, exports: list | None) -> list:
    """`public` means exported from its file (S9). With `exports` None the reducer's value is kept. Symbols lose package and version."""
    names: dict = {}
    for e in exports or []:
        names.setdefault(e["path"], set()).update({e["name"], e.get("local") or e["name"]})
    out = []
    for i in items:
        if i["kind"] != "def":
            out.append(i)
            continue
        row = {**i}
        top = _top_level(i["symbol"])
        if exports is not None and top is not None:
            row["public"] = top in names.get(i["path"], set())
        row["symbol"] = _anonymous(i["symbol"])
        out.append(row)
    return out


_ENTITY_KINDS = {"interface": "ts-interface", "type": "ts-type", "enum": "ts-enum"}


def _is_entity(t: dict, test_re) -> bool:
    path = t["path"]
    if not t.get("exported") or t["name"].endswith("Props"):
        return False
    if path.endswith(".d.ts") or test_re.search(path) or ".stories." in path:
        return False
    if t["kind"] == "class":
        return "Entity" in t.get("decorators", [])
    return t["kind"] != "type" or bool(t.get("object"))


def model_items(types: list, test_re=None) -> list:
    """Entities from the TypeScript script's `types`: exported interfaces, object types, enums and `@Entity` classes (D7, S10)."""
    test_re = test_re or gather.TEST_RE
    kept = [t for t in types if _is_entity(t, test_re)]
    names = {t["name"] for t in kept}
    items = []
    for t in kept:
        kind = "typeorm" if t["kind"] == "class" else _ENTITY_KINDS[t["kind"]]
        fields = []
        for f in t.get("fields", []):
            words = re.findall(r"[A-Za-z_]\w*", f.get("type") or "")
            fields.append({"name": f["name"], "type": f.get("type") or None, "line": f["line"],
                           "ref": next((w for w in words if w in names and w != t["name"]), None)})
        items.append({"path": t["path"], "line": t["line"], "end_line": t["end_line"], "name": t["name"], "kind": kind, "rule": kind,
                      "snippet": f"{t['kind']} {t['name']}", "bases": t.get("bases", []), "fields": fields})
    return sorted(items, key=lambda i: (i["path"], i["line"]))


def ui_items(components: list, tree) -> list:
    """`ui-component` items, and a `renders` item for each component that renders one defined in the repository."""
    tracked = set(tree)
    items = []
    for c in sorted(components, key=lambda c: (c["path"], c["line"], c["name"])):
        items.append({"kind": "ui-component", "path": c["path"], "line": c["line"], "end_line": c.get("end_line", c["line"]), "name": c["name"],
                      "exported": c["exported"], "hooks": c["hooks"], "provides": c["provides"], "consumes": c["consumes"]})
        for r in c["renders"]:
            if r["path"] and r["path"] in tracked:
                items.append({"kind": "renders", "path": c["path"], "paths": [r["path"]], "from": c["name"], "to": r["name"]})
    return items


def render_edges(items: list) -> list:
    """`ref-edge` symbols from `renders` items between two different files, so an arrow can be backed when scip-typescript did not run."""
    counts: dict = {}
    for i in items:
        if i["kind"] == "renders" and i["paths"][0] != i["path"]:
            counts[(i["path"], i["paths"][0])] = counts.get((i["path"], i["paths"][0]), 0) + 1
    return [{"kind": "ref-edge", "path": a, "paths": [b], "count": n} for (a, b), n in sorted(counts.items())]


def route_parts(detail: str) -> tuple:
    """(METHOD, path) from a rule's `detail` such as ``get('/tags``; the method is upper-cased."""
    detail = re.sub(r"//[^\n]*\n|/\*.*?\*/", "", detail, flags=re.S)
    found = re.match(r"""\s*\.?(\w+)\(\s*[`'"]?(.*)$""", detail, re.S)
    return (found.group(1).upper(), found.group(2).strip()) if found else ("", detail.strip())


def route_entries(routes: list) -> list:
    """`ui-route` entry points from the TypeScript script's routes. An unresolved route keeps its source text as the name."""
    return [{"path": r["path"], "line": r["line"], "end_line": r.get("end_line", r["line"]), "kind": "ui-route", "name": r["route"],
             "trigger": f"opening `{r['route']}` in the browser", "target": r.get("file") or r["path"],
             "rule": "js.react-router" if r.get("framework") == "react-router" else f"js.{r.get('framework') or 'router'}", "snippet": r["route"][:200]}
            for r in routes]
