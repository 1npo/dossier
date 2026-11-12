"""The tables of the two measured graph cards (D4): the component edge table and the module table."""
from __future__ import annotations
from dossier.render import markup

__all__ = [
    "API_COLUMNS", "REACT_COLUMNS", "component_edges", "config_keys", "friend_lines", "heading", "module_imports",
    "public_api", "public_api_rows", "react_components",
]


def heading(text: str) -> str:
    return f'<h4 class="graph-heading">{markup.E(text)}</h4>'


def component_edges(cid: str, imports: list, group: dict, refs, kind: str) -> str:
    """Every edge between components (or areas): imports and the number of importing files, most imports first."""
    pairs: dict = {}
    for a, b in imports:
        ga, gb = group.get(a), group.get(b)
        if ga is None or gb is None or ga == gb:
            continue
        pairs.setdefault((ga, gb), []).append(a)
    ordered = sorted(pairs.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    rows = [[markup.E(ga), markup.E(gb), (str(len(files)), len(files)), (str(len(set(files))), len(set(files)))] for (ga, gb), files in ordered]
    return markup.render_table([f"From {kind}", f"To {kind}", "Imports", "Modules"], rows, refs, "t-" + cid.replace(".", "-") + "-components", plain=True)


def module_imports(cid: str, items: list, group: dict, refs, kind: str) -> str:
    """Every module import, by the component it comes from."""
    rows = []
    for g in sorted(items, key=lambda g: (group.get(g["path"], ""), g["path"], g["to"])):
        lines = g.get("lines") or []
        places = markup.source_cell(refs, *[(g["path"], n) for n in lines]) if lines else markup.source_cell(refs, (g["path"], None))
        rows.append([markup.E(group.get(g["path"], "-")), markup.E(group.get(g["paths"][0], "-")), markup.E(g["from"]), markup.E(g["to"]),
                     (str(max(len(lines), 1)), max(len(lines), 1)), places])
    return markup.render_table([f"From {kind}", f"To {kind}", "From", "To", "Imports", "Source"], rows, refs, "t-" + cid.replace(".", "-") + "-edges", plain=True)


REACT_COLUMNS = ["Component", "File", "Renders", "Rendered by", "Hooks", "Context", "Source"]


def _names(values) -> str:
    return ", ".join(sorted(set(values))) or "-"


def react_components(cid: str, extract: dict, refs) -> str:
    """Every React component with what it renders, what renders it, its hooks and its context, from the `ui-component` and `renders` items."""
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
        rows.append([markup.E(c["name"]), markup.path_code(c["path"]), markup.E(_names(n for _, n in drawn.get(key, []))), markup.E(_names(rendered_by.get(key, []))),
                     markup.E(_names(c.get("hooks") or [])), markup.E("; ".join(context) or "-"), markup.source_cell(refs, (c["path"], c.get("line")))])
    return markup.render_table(REACT_COLUMNS, rows, refs, "t-" + cid.replace(".", "-") + "-react", plain=True)


API_COLUMNS = ["Package", "Import path", "Name", "Kind", "Defined in", "Audience", "Source"]
NO_API = "No package here declares a public API. What this repository offers from outside is in Entry points."


def public_api_rows(extract: dict) -> list:
    """The `public-api` symbols, one per (package, import path, name), sorted by package, subpath, name."""
    seen: dict = {}
    for s in extract.get("symbols", []):
        if s.get("kind") == "public-api":
            seen.setdefault((s["package"], s["subpath"], s["name"]), s)
    return [seen[k] for k in sorted(seen)]


def friend_lines(extract: dict) -> list:
    """One sentence per (packable C# project, friend assembly) that the project's `InternalsVisibleTo` names (D15), sorted."""
    pairs = {(g["name"], f) for g in extract.get("graph", []) if g.get("kind") == "cs-project" and g.get("packable") for f in g.get("friends") or []}
    return [f"{p} lets {f} use its internal names (InternalsVisibleTo)." for p, f in sorted(pairs)]


def public_api(ctx: dict, refs) -> str:
    """The table of what other packages can import (D17), then the `InternalsVisibleTo` lines (D15).

    Empty for a repository with no JavaScript or C#; one line when it declares nothing."""
    extract = ctx.get("extract") or {}
    found = public_api_rows(extract)
    lines = "".join(f'<p class="muted">{markup.E(x)}</p>' for x in friend_lines(extract))
    if not found:
        has_code = any(g.get("kind") == "module" for g in extract.get("graph", []))  # Python, JavaScript or C#
        return (f'<p class="muted">{NO_API}</p>' if has_code else "") + lines
    rows = []
    for s in found:
        if s["subpath"].startswith("."):  # JavaScript: the subpath is relative to the package
            sub = s["subpath"][1:]
            importable = s["package"] + sub
        else:  # C#: the subpath is the namespace
            importable = s["subpath"] or s["package"]
        where = markup.path_code(s["path"]) if s.get("path") and not s.get("external") else markup.E(f"from {s['external']}") if s.get("external") else "-"
        rows.append([markup.E(s["package"]), markup.E(importable), markup.E(s["name"]), markup.E(s["symbol_kind"]), where, markup.E(s["audience"]),
                     markup.source_cell(refs, (s["path"], s.get("line"))) if s.get("path") and not s.get("external") else ""])
    return heading("Public API of each package") + markup.render_table(API_COLUMNS, rows, refs, "t-io-contracts-api", plain=True) + lines


CONFIG_COLUMNS = ["Name", "Kind", "Read at", "Source"]
CONFIG_KINDS = {"dossier.csharp.config.config-key": "key", "dossier.csharp.config.config-binding": "options class"}


def config_key_rows(extract: dict) -> list:
    """`config-key` findings grouped by (name, kind): [(name, kind, [(path, line), ...])], sorted. A name is a literal key or an options class; a value is never stored."""
    groups: dict = {}
    for i in extract.get("io_candidates", []):
        if i.get("category") == "config-key":
            name = i.get("detail") or i.get("snippet") or "?"
            groups.setdefault((name, CONFIG_KINDS.get(i.get("rule"), "key")), set()).add((i["path"], i["line"]))
    return [(n, k, sorted(places)) for (n, k), places in sorted(groups.items())]


def config_keys(ctx: dict, refs) -> str:
    """The group under the Inputs card: configuration read by name (C# `IConfiguration`, `GetSection`, `Bind`, `IOptions<T>`). Empty when there are none.

    These are not environment variables, so the environment-variable card skips them. Every row is listed; only names are shown."""
    rows = config_key_rows(ctx.get("extract") or {})
    if not rows:
        return ""
    body = [[(f"<code>{markup.E(n)}</code>", n), markup.E(k), "<br>".join(f"{markup.path_code(p)}:{ln}" for p, ln in places), markup.source_cell(refs, *places)] for n, k, places in rows]
    note = ('<p class="muted">Configuration read by name, as a key or through an options class. These are not environment variables. '
            'Values are never shown: a key set in <code>appsettings.json</code> or an environment variable is not read here.</p>')
    return heading("Configuration keys") + note + markup.render_table(CONFIG_COLUMNS, body, refs, "t-io-inputs-config", plain=True)
