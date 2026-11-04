"""The tables of the two measured graph cards (D4): the component edge table and the module table."""
from __future__ import annotations


def _render():
    import render  # imported late: render imports measured, which imports this module

    return render


def heading(text: str) -> str:
    return f'<h4 class="graph-heading">{_render().E(text)}</h4>'


def component_edges(cid: str, imports: list, group: dict, refs, kind: str) -> str:
    """Every edge between components (or areas): imports and the number of importing files, most imports first."""
    r = _render()
    pairs: dict = {}
    for a, b in imports:
        ga, gb = group.get(a), group.get(b)
        if ga is None or gb is None or ga == gb:
            continue
        pairs.setdefault((ga, gb), []).append(a)
    ordered = sorted(pairs.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    rows = [[r.E(ga), r.E(gb), (str(len(files)), len(files)), (str(len(set(files))), len(set(files)))] for (ga, gb), files in ordered]
    return r.render_table([f"From {kind}", f"To {kind}", "Imports", "Modules"], rows, refs, "t-" + cid.replace(".", "-") + "-components", plain=True)


def module_imports(cid: str, items: list, group: dict, refs, kind: str) -> str:
    """Every module import, by the component it comes from."""
    r = _render()
    rows = []
    for g in sorted(items, key=lambda g: (group.get(g["path"], ""), g["path"], g["to"])):
        lines = g.get("lines") or []
        places = r.source_cell(refs, *[(g["path"], n) for n in lines]) if lines else r.source_cell(refs, (g["path"], None))
        rows.append([r.E(group.get(g["path"], "-")), r.E(group.get(g["paths"][0], "-")), r.E(g["from"]), r.E(g["to"]),
                     (str(max(len(lines), 1)), max(len(lines), 1)), places])
    return r.render_table([f"From {kind}", f"To {kind}", "From", "To", "Imports", "Source"], rows, refs, "t-" + cid.replace(".", "-") + "-edges", plain=True)
