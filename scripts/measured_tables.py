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


REACT_COLUMNS = ["Component", "File", "Renders", "Rendered by", "Hooks", "Context", "Source"]


def _names(values) -> str:
    return ", ".join(sorted(set(values))) or "-"


def react_components(cid: str, extract: dict, refs) -> str:
    """Every React component with what it renders, what renders it, its hooks and its context, from the `ui-component` and `renders` items."""
    r = _render()
    graph = extract.get("graph", [])
    comps = sorted((g for g in graph if g.get("kind") == "ui-component"), key=lambda g: (g["path"], g["name"], g.get("line") or 0))
    in_file: dict = {}
    for c in comps:
        in_file.setdefault(c["path"], []).append(c)
    drawn: dict = {}
    for e in (g for g in graph if g.get("kind") == "renders" and g.get("paths")):
        here = in_file.get(e["paths"][0], [])
        named = [c for c in here if c["name"] == e["to"]]
        target = named[0] if named else here[0] if len(here) == 1 else None  # a renamed import still points at the file's only component
        if target is not None:
            drawn.setdefault((e["path"], e["from"]), []).append((target["path"], target["name"]))
    rendered_by: dict = {}
    for (path, name), targets in drawn.items():
        for t in targets:
            rendered_by.setdefault(t, []).append(name)
    rows = []
    for c in comps:
        key = (c["path"], c["name"])
        context = [f"provides {x}" for x in sorted(set(c.get("provides") or []))] + [f"uses {x}" for x in sorted(set(c.get("consumes") or []))]
        rows.append([r.E(c["name"]), r.path_code(c["path"]), r.E(_names(n for _, n in drawn.get(key, []))), r.E(_names(rendered_by.get(key, []))),
                     r.E(_names(c.get("hooks") or [])), r.E("; ".join(context) or "-"), r.source_cell(refs, (c["path"], c.get("line")))])
    return r.render_table(REACT_COLUMNS, rows, refs, "t-" + cid.replace(".", "-") + "-react", plain=True)


API_COLUMNS = ["Package", "Import path", "Name", "Kind", "Defined in", "Audience", "Source"]
NO_API = "No package here declares a public API. What this repository offers from outside is in Entry points."


def public_api_rows(extract: dict) -> list:
    """The `public-api` symbols, one per (package, import path, name), sorted by package, subpath, name."""
    seen: dict = {}
    for s in extract.get("symbols", []):
        if s.get("kind") == "public-api":
            seen.setdefault((s["package"], s["subpath"], s["name"]), s)
    return [seen[k] for k in sorted(seen)]


def public_api(ctx: dict, refs) -> str:
    """The table of what other packages can import (D17): empty for a repository without JavaScript, one line when it declares nothing."""
    extract = ctx.get("extract") or {}
    found = public_api_rows(extract)
    if not found:
        return f'<p class="muted">{NO_API}</p>' if any(g.get("language") == "js" for g in extract.get("graph", []) if g.get("kind") == "module") else ""
    r = _render()
    rows = []
    for s in found:
        sub = s["subpath"][1:] if s["subpath"].startswith(".") else s["subpath"]
        where = r.path_code(s["path"]) if s.get("path") and not s.get("external") else r.E(f"from {s['external']}") if s.get("external") else "-"
        rows.append([r.E(s["package"]), r.E(s["package"] + sub), r.E(s["name"]), r.E(s["symbol_kind"]), where, r.E(s["audience"]),
                     r.source_cell(refs, (s["path"], s.get("line"))) if s.get("path") and not s.get("external") else ""])
    return heading("Public API of each package") + r.render_table(API_COLUMNS, rows, refs, "t-io-contracts-api", plain=True)
