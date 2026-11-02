"""The two measured graph cards (D8): `components.map` and `interactions.graph`.

Both draw component-level Mermaid flowcharts (one arrow per pair of components with at least one import; a graph over the
budget is split into an overview of areas and one diagram per area) and tables that hold every fact, so nothing is dropped:
the dependency matrix, the component edge table and the module table. Collapsible graphs come in a later milestone.
"""
from __future__ import annotations

import re

import components
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
    """Folders of the top-level Python packages, longest first (`src/cannalerts`)."""
    roots = {m["path"].rsplit("/", 1)[0] for m in extract.get("graph", [])
             if m.get("kind") == "module" and m.get("is_package") and m.get("package") == m.get("module") and "/" in m["path"]}
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


MAX_NODES, MAX_EDGES = 12, 30


def _flowchart(edges, area_of_group: dict | None, extra=(), direction="TB") -> str:
    """One flowchart: a subgraph per area when `area_of_group` is given, a plain arrow (no label) per pair of nodes."""
    taken: dict = {}
    nodes = sorted({n for pair in edges for n in pair} | set(extra))
    lines = [f"flowchart {direction}"]
    by_area: dict = {}
    for n in nodes:
        by_area.setdefault((area_of_group or {}).get(n), []).append(n)
    for area, members in sorted(by_area.items(), key=lambda kv: (kv[0] is None, kv[0] or "")):
        indent = "  "
        if area is not None:
            lines.append(f'  subgraph {mermaid_id("g_" + area, taken)}["{_label(area)}"]')
            indent = "    "
        lines += [f'{indent}{mermaid_id(n, taken)}["{_label(n)}"]' for n in members]
        if area is not None:
            lines.append("  end")
    for (a, b) in sorted(edges):
        lines.append(f"  {mermaid_id(a, taken)} --> {mermaid_id(b, taken)}")
    return "\n".join(lines)


def _overview(edges: dict, area: dict, nodes) -> str:
    taken: dict = {}
    areas = sorted({area[n] for n in nodes})
    pairs = sorted({(area[a], area[b]) for (a, b) in edges if area[a] != area[b]})
    lines = ["flowchart TB"] + [f'  {mermaid_id(a, taken)}["{_label(a)}"]' for a in areas]
    lines += [f"  {mermaid_id(a, taken)} --> {mermaid_id(b, taken)}" for a, b in pairs]
    return "\n".join(lines)


def _area_diagram(name: str, edges: dict, area: dict, nodes) -> str:
    taken: dict = {}
    members = sorted(n for n in nodes if area[n] == name)
    outside = {area[x] for pair in edges for x in pair if area[x] != name and any(area[y] == name for y in pair)}
    lines = ["flowchart TB", f'  subgraph {mermaid_id("g_" + name, taken)}["{_label(name)}"]']
    lines += [f'    {mermaid_id("c " + n, taken)}["{_label(n)}"]' for n in members]
    lines.append("  end")
    lines += [f'  {mermaid_id("a " + o, taken)}["{_label(o)} (area)"]' for o in sorted(outside)]
    arrows = set()
    for (a, b) in edges:
        ida = mermaid_id("c " + a, taken) if area[a] == name else mermaid_id("a " + area[a], taken)
        idb = mermaid_id("c " + b, taken) if area[b] == name else mermaid_id("a " + area[b], taken)
        if area[a] == name or area[b] == name:
            arrows.add((ida, idb))
    lines += [f"  {a} --> {b}" for a, b in sorted(arrows)]
    return "\n".join(lines)


def diagrams(edges: dict, area: dict | None, extra=(), title="Imports between components") -> list:
    """The diagrams for a component graph: [(title, mermaid source, budget)].

    A graph of at most MAX_NODES nodes and MAX_EDGES edges is one diagram. A larger one is an overview with one node per area
    plus one diagram per area (its components, and a node for each other area they import or are imported by). `budget` is
    "area" for a diagram that may be over budget (an overview, an area, or a graph with no areas to split by), else "".
    Every edge is in an area diagram, and in the overview as an edge between areas.
    """
    nodes = {n for pair in edges for n in pair} | set(extra)
    within = len(nodes) <= MAX_NODES and len(edges) <= MAX_EDGES
    if within:
        return [(title, _flowchart(edges, area, extra), "")]
    if not area:
        return [(title, _flowchart(edges, None, extra), "area")]
    out = [(f"{title}: areas", _overview(edges, area, nodes), "area")]
    out += [(f"{title}: {name}", _area_diagram(name, edges, area, nodes), "area") for name in sorted({area[n] for n in nodes})]
    return out


def _diagram(title: str, source: str, budget: str = "") -> str:
    r = _render()
    mark = f' data-budget="{budget}"' if budget else ""
    return (f'<div class="diagram flow"><div class="flow-bar"><h4>{r.E(title)}</h4><div class="card-action"><button class="btn" data-variant="ghost" data-size="sm" '
            f'type="button" data-expand title="Expand" aria-label="Expand diagram">{r.EXPAND_ICONS}</button></div></div>'
            f'<div class="mermaid-host"{mark} data-src="{r.E(source)}"><pre class="muted">Diagram loads when this report is opened.</pre></div>'
            f'<details><summary class="muted">Diagram source</summary><pre>{r.E(source)}</pre></details></div>')


def _charts(edges: dict, area: dict | None, extra, title: str) -> str:
    if len({n for pair in edges for n in pair}) < 2:
        return ""
    return "".join(_diagram(t, src, budget) for t, src, budget in diagrams(edges, area, extra, title))


def _area_map(rows: list, roots: list) -> dict:
    return {**{row["name"]: component_area(row["paths"], roots) for row in rows}, UNASSIGNED: UNASSIGNED}


def _graph(cid, ctx, refs):
    extract = ctx.get("extract") or {}
    if "graph" not in extract:
        return None
    if not _imports(extract):
        return '<p class="muted">No imports between modules were found.</p>'
    rows, roots = ctx.get("catalog") or [], package_roots(extract)
    group = _group_of(extract, rows, roots)
    imports = [(g["path"], g["paths"][0]) for g in _imports(extract)]
    edges = graphs.aggregate(imports, group)
    area = _area_map(rows, roots) if rows else None
    charts = _charts(edges, area, (), "Imports between components" if rows else "Imports between areas")
    kind = "component" if rows else "area"
    return (charts + measured_tables.heading(f"Imports between {kind}s")
            + measured_tables.component_edges(cid, imports, group, refs, kind)
            + measured_tables.heading("Every module import")
            + measured_tables.module_imports(cid, _imports(extract), group, refs, kind))


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
    names = [row["name"] for row in rows]
    charts = _charts(edges, area, names, "Components and what they import")
    return (charts + r.render_table(["Component", "Area", "Files", "Lines", "Depends on", "Used by"], table, refs, "t-" + cid.replace(".", "-"), plain=True)
            + measured_tables.heading("Dependency matrix")
            + measured_tables.matrix(cid, names, edges, area, refs))


DRAWN = {"interactions.graph": _graph, "components.map": _map}
