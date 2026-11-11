"""The two measured graph cards (D8): `components.map` and `interactions.graph`.

Both hold tables that carry every fact, so nothing is dropped: the component table, the component edge table and
the module table. Above the tables sits an interactive graph (plan 012, D7): `graph_views` computes every collapsible view
and the page script only switches between them. (`_diagram` also draws the entity-relationship diagrams of `measured_er`.)
"""
from __future__ import annotations

import json
import re

import components
import graph_views
import graphs
import measured_tables

UNASSIGNED = "unassigned"


def _render():
    import render  # imported late: render imports measured, which imports this module

    return render


def mermaid_id(name: str, taken: dict | None = None) -> str:
    """A node id that Mermaid accepts: letters, digits and underscores. Two names never share an id when `taken` is passed."""
    ident = re.sub(r"[^A-Za-z0-9_]", "_", name) or "n"
    ident = "n_" + ident if ident[0].isdigit() else ident
    if taken is not None:
        base, n = ident, 1
        while taken.get(ident, name) != name:
            n += 1
            ident = f"{base}_{n}"
        taken[ident] = name
    return ident


def _label(text: str) -> str:
    return str(text).replace('"', "#quot;")


def package_roots(extract: dict) -> list:
    """Folders of the top-level Python packages and the JavaScript source roots, longest first (`src/cannalerts`, `apps`)."""
    roots = {m["path"].rsplit("/", 1)[0] for m in extract.get("graph", [])
             if m.get("kind") == "module" and m.get("is_package") and m.get("package") == m.get("module") and "/" in m["path"]}
    roots |= {g["root"] for g in extract.get("graph", []) if g.get("kind") == "source-root" and g.get("root")}
    return sorted(roots, key=lambda r: (-len(r), r))


def area_of(path: str, roots: list) -> str:
    """The first folder below the package root, or the top-level folder (a file at the root is in "(top level)")."""
    stripped = path.rstrip("/")
    for root in roots:
        if stripped == root:
            return root.rsplit("/", 1)[-1]
        if stripped.startswith(root + "/"):
            return stripped[len(root) + 1:].split("/")[0]
    return stripped.split("/")[0] if "/" in stripped else "(top level)"


def _area_of_path(path: str, roots: list) -> str:
    stripped = path.rstrip("/")
    is_file = not path.endswith("/") and "." in stripped.rsplit("/", 1)[-1]
    for root in roots:
        pkg = root.rsplit("/", 1)[-1]
        if stripped == root:
            return pkg
        if stripped.startswith(root + "/"):
            parts = stripped[len(root) + 1:].split("/")
            return f"{pkg} (top-level modules)" if len(parts) == 1 and is_file else parts[0]
    parts = stripped.split("/")
    return "(repository root)" if len(parts) == 1 and is_file else parts[0]


def component_area(paths: list, roots: list) -> str:
    """A component's area: the first folder below its package root that holds its paths (the first path's, when they differ).

    Files directly in a package root are "<package> (top-level modules)"; files at the repository root are "(repository root)".
    """
    return _area_of_path(paths[0], roots) if paths else "(repository root)"


def _imports(extract: dict) -> list:
    return [g for g in extract.get("graph", []) if g.get("kind") == "import" and g.get("paths")]


def _group_of(extract: dict, rows: list, roots: list) -> dict:
    """File path -> component name (or, without a catalog, its area) for every file that takes part in an import."""
    out = {}
    for g in _imports(extract):
        for p in (g["path"], g["paths"][0]):
            if rows:
                out[p] = components.component_of(p, rows)[0] or UNASSIGNED
            else:
                out[p] = area_of(p, roots)
    return out


def _diagram(title: str, source: str, budget: str = "") -> str:
    r = _render()
    mark = f' data-budget="{budget}"' if budget else ""
    return (f'<div class="diagram flow"><div class="flow-bar"><h4>{r.E(title)}</h4><div class="card-action"><button class="btn" data-variant="ghost" data-size="sm" '
            f'type="button" data-expand title="Expand" aria-label="Expand diagram">{r.EXPAND_ICONS}</button></div></div>'
            f'<div class="mermaid-host"{mark} data-src="{r.E(source)}"><pre class="muted">Diagram loads when this report is opened.</pre></div>'
            f'<details><summary class="muted">Diagram source</summary><pre>{r.E(source)}</pre></details></div>')


NO_JS = "The interactive graph needs JavaScript. Every component and link is in the tables below."


def _json(data) -> str:
    """JSON for a `<script>` element: `<` and `&` are escaped so the text can never close the tag."""
    return json.dumps(data, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c").replace("&", "\\u0026")


def igraph(title: str, found: list) -> str:
    """The interactive graph block: data, toolbar, host, caption and one open button per node of the root view that has a view."""
    if not found:
        return ""
    r = _render()
    root = found[0]
    options = "".join(f'<option value="{r.E(v["id"])}"{" selected" if v is root else ""}>{r.E(v["title"])}</option>' for v in found)
    opens = "".join(f'<button class="btn" data-variant="ghost" data-size="sm" type="button" data-open="{r.E(n["view"])}">Open {r.E(n["label"])}</button>'
                    for n in root["nodes"] if n["view"])
    return (f'<div class="diagram flow igraph"><script type="application/json" class="igraph-data">{_json(found)}</script>'
            f'<div class="flow-bar"><h4>{r.E(title)}</h4></div>'
            f'<div class="igraph-bar"><span class="igraph-crumb">{r.E(root["title"])}</span>'
            f'<button class="btn igraph-up" data-variant="ghost" data-size="sm" type="button" hidden>Up</button>'
            f'<label class="igraph-pick">View <select class="igraph-select">{options}</select></label></div>'
            f'<div class="mermaid-host" data-src="{r.E(root["src"])}"><p class="muted">{NO_JS}</p></div>'
            f'<p class="igraph-caption muted"></p><div class="igraph-open">{opens}</div></div>')


def _area_map(rows: list, roots: list) -> dict:
    return {**{row["name"]: component_area(row["paths"], roots) for row in rows}, UNASSIGNED: UNASSIGNED}


def _component_views(rows: list, area: dict, edges: dict) -> list:
    """Areas -> components. Keys carry a prefix so an area and a component may share a name."""
    names = [row["name"] for row in rows] + [UNASSIGNED]
    levels = {**{"a:" + a: None for a in {area[n] for n in names}}, **{"c:" + n: "a:" + area[n] for n in names}}
    labels = {k: k[2:] for k in levels}
    return graph_views.views(levels, {("c:" + a, "c:" + b): w for (a, b), w in edges.items()}, "All areas", ("area", "component"), labels)


def _module_views(rows: list, roots: list, group: dict, imports: list) -> list:
    """Areas -> components -> modules, or areas -> modules without a catalog. Edge weights count imports between two files."""
    area = _area_map(rows, roots) if rows else {}
    levels, labels = {}, {}
    for path, name in group.items():
        a = "a:" + (area.get(name, UNASSIGNED) if rows else name)
        levels[a], labels[a] = None, a[2:]
        parent = a
        if rows:
            parent = "c:" + name
            levels[parent], labels[parent] = a, name
        levels["m:" + path], labels["m:" + path] = parent, path
    pairs: dict = {}
    for a, b in imports:
        if a != b:
            pairs[("m:" + a, "m:" + b)] = pairs.get(("m:" + a, "m:" + b), 0) + 1
    kinds = ("area", "component", "module") if rows else ("area", "module")
    return graph_views.views(levels, pairs, "All areas", kinds, labels)


def _graph(cid, ctx, refs):
    extract = ctx.get("extract") or {}
    if "graph" not in extract:
        return None
    react = ""
    if any(g.get("kind") == "ui-component" for g in extract["graph"]):  # only for a repository that has React components
        react = measured_tables.heading("Every React component") + measured_tables.react_components(cid, extract, refs)
    if not _imports(extract):
        return '<p class="muted">No imports between modules were found.</p>' + react
    rows, roots = ctx.get("catalog") or [], package_roots(extract)
    group = _group_of(extract, rows, roots)
    imports = [(g["path"], g["paths"][0]) for g in _imports(extract)]
    kind = "component" if rows else "area"
    return (igraph("Dependency graph", _module_views(rows, roots, group, imports))
            + measured_tables.heading(f"Imports between {kind}s")
            + measured_tables.component_edges(cid, imports, group, refs, kind)
            + measured_tables.heading("Every module import")
            + measured_tables.module_imports(cid, _imports(extract), group, refs, kind)
            + react)


def _map(cid, ctx, refs):
    rows, extract = ctx.get("catalog") or [], ctx.get("extract") or {}
    if not rows or "graph" not in extract:
        return None
    r = _render()
    roots = package_roots(extract)
    area = _area_map(rows, roots)
    group = _group_of(extract, rows, roots)
    edges = graphs.aggregate([(g["path"], g["paths"][0]) for g in _imports(extract)], group)
    files = components.source_files(ctx.get("tree"), extract)
    lines = components.file_lines(ctx.get("facts") or {})
    owner = {p: components.component_of(p, rows)[0] for p in files}
    uses, used = {}, {}
    for (a, b) in edges:
        uses.setdefault(a, []).append(b)
        used.setdefault(b, []).append(a)
    table = []
    for row in rows:
        name = row["name"]
        mine = [p for p in files if owner[p] == name]
        table.append([r.E(name), r.E(area[name]), (str(len(mine)), len(mine)), (str(sum(lines.get(p, 0) for p in mine)), sum(lines.get(p, 0) for p in mine)),
                      r.E(", ".join(sorted(uses.get(name, [])))) or "-", r.E(", ".join(sorted(used.get(name, [])))) or "-"])
    graph = igraph("Component map", _component_views(rows, area, edges)) if edges else ""
    return graph + r.render_table(["Component", "Area", "Files", "Lines", "Depends on", "Used by"], table, refs, "t-" + cid.replace(".", "-"), plain=True)


DRAWN = {"interactions.graph": _graph, "components.map": _map}
