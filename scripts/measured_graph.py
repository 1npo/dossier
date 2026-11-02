"""The two measured graph cards (D8): `components.map` and `interactions.graph`.

Both draw a component-level Mermaid flowchart (one arrow per pair of components with at least one import, labelled with the
count) and a table that holds every module-level fact, so nothing is dropped. Collapsible graphs come in a later milestone.
"""
from __future__ import annotations

import re

import components
import graphs

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


def _flowchart(edges: dict, area_of_group: dict | None, extra=()) -> str:
    taken: dict = {}
    nodes = sorted({n for pair in edges for n in pair} | set(extra))
    lines = ["flowchart LR"]
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
    for (a, b), count in sorted(edges.items()):
        lines.append(f'  {mermaid_id(a, taken)} -->|"{count} import{"" if count == 1 else "s"}"| {mermaid_id(b, taken)}')
    return "\n".join(lines)


def _diagram(title: str, source: str) -> str:
    r = _render()
    return (f'<div class="diagram flow"><div class="flow-bar"><h4>{r.E(title)}</h4><div class="card-action"><button class="btn" data-variant="ghost" data-size="sm" '
            f'type="button" data-expand title="Expand" aria-label="Expand diagram">{r.EXPAND_ICONS}</button></div></div>'
            f'<div class="mermaid-host" data-src="{r.E(source)}"><pre class="muted">Diagram loads when this report is opened.</pre></div>'
            f'<details><summary class="muted">Diagram source</summary><pre>{r.E(source)}</pre></details></div>')


def _edge_table(cid, extract, refs):
    r = _render()
    rows = []
    for g in sorted(_imports(extract), key=lambda g: (g["path"], g["to"])):
        lines = g.get("lines") or []
        places = ", ".join(r.path_cell(g["path"], refs, n) for n in lines) if lines else r.path_cell(g["path"], refs)
        rows.append([r.E(g["from"]), r.E(g["to"]), (str(max(len(lines), 1)), max(len(lines), 1)), places])
    return r.render_table(["From", "To", "Imports", "Lines"], rows, refs, "t-" + cid.replace(".", "-") + "-edges", plain=True)


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
    title = "Imports between components" if rows else "Imports between areas"
    chart = _diagram(title, _flowchart(edges, None)) if len({n for pair in edges for n in pair}) >= 2 else ""
    return chart + _edge_table(cid, extract, refs)


def _map(cid, ctx, refs):
    rows, extract = ctx.get("catalog") or [], ctx.get("extract") or {}
    if not rows or "graph" not in extract:
        return None
    r = _render()
    roots = package_roots(extract)
    area = {row["name"]: component_area(row["paths"], roots) for row in rows}
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
    chart = _diagram("Components and what they import", _flowchart(edges, {**area, UNASSIGNED: UNASSIGNED}, area)) if edges else ""
    return chart + r.render_table(["Component", "Area", "Files", "Lines", "Depends on", "Used by"], table, refs, "t-" + cid.replace(".", "-"), plain=True)


DRAWN = {"interactions.graph": _graph, "components.map": _map}
