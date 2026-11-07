"""The `data.relationships` card, drawn from the extracted models (D9): every entity with every field, every relation.

SQL tables come from CREATE TABLE statements (columns, primary keys, foreign keys); Python classes come from the model
extractor, and a field whose `ref` names another entity is a relation. A set of more than 12 entities is split into one
diagram per owner component (or per area without a catalog) plus one for the SQL tables. A table under the diagrams lists every
field, so nothing is left out of the card even where the picture is split.
"""
from __future__ import annotations

import re
from collections import Counter

import components
import measured_graph
import measured_tables

MAX_ENTITIES = 12
SQL = "sql-table"


def _render():
    import render  # imported late: render imports measured, which imports this module

    return render


def entities(extract: dict) -> list:
    """Every entity (migrations are not), once per (path, name), in path and line order."""
    seen, out = set(), []
    for m in sorted((m for m in extract.get("models", []) if m.get("kind") != "migration" and m.get("name")), key=lambda m: (m["path"], m.get("line") or 0)):
        if (m["path"], m["name"]) not in seen:
            seen.add((m["path"], m["name"]))
            out.append(m)
    return out


def family(entity: dict) -> str:
    """Which kind of source an entity comes from, so a relation joins an entity only to one of its own family."""
    kind = entity["kind"]
    return "sql" if kind == SQL else "prisma" if kind in ("prisma", "prisma-enum") else "other"


def safe_type(text) -> str:
    """A type Mermaid accepts as an attribute type: letters, digits and underscores. `str | None` becomes `str_or_None`."""
    t = re.sub(r"[^A-Za-z0-9_]+", "_", re.sub(r"\s*\|\s*", "_or_", str(text or ""))).strip("_")
    return ("t_" + t if t[:1].isdigit() else t) or "any"


def safe_name(text) -> str:
    """An attribute name Mermaid accepts: it cannot start with a digit."""
    n = re.sub(r"[^A-Za-z0-9_]+", "_", str(text or "")).strip("_") or "field"
    return "f_" + n if n[0].isdigit() else n


def _keys(field: dict) -> str:
    return ", ".join(k for k, on in (("PK", field.get("pk")), ("FK", field.get("ref") and True)) if on)


def _relations(group: list, everything: list, idents: dict) -> list:
    """(parent ident, child ident, label, cardinality) for every relation of an entity in `group` to a known entity."""
    by_name: dict = {}
    for e in everything:
        by_name.setdefault((family(e), e["name"]), e)
    out = []
    for e in group:
        for f in e.get("fields") or []:
            target = by_name.get((family(e), f.get("ref"))) if f.get("ref") else None
            if target is None:
                continue
            out.append((e, target, f["name"]))
    return out


def _source(group: list, everything: list, owner_of) -> str:
    taken: dict = {}
    count = Counter(e["name"] for e in everything)
    idents = {id(e): measured_graph.mermaid_id(e["name"] if count[e["name"]] == 1 else f"{e['name']} {e['path']}", taken) for e in everything}
    inside = {id(e) for e in group}
    rels = _relations(group, everything, idents)
    outside = {id(t): t for _, t, _ in rels if id(t) not in inside}
    lines = ["erDiagram"]
    for e in group:
        label = measured_graph._label(e["name"])
        fields = e.get("fields") or []
        if not fields:
            lines.append(f'  {idents[id(e)]}["{label}"]')
            continue
        lines.append(f'  {idents[id(e)]}["{label}"] {{')
        lines += [f"    {safe_type(f.get('type'))} {safe_name(f['name'])}{' ' + _keys(f) if _keys(f) else ''}" for f in fields]
        lines.append("  }")
    for t in outside.values():
        lines.append(f'  {idents[id(t)]}["{measured_graph._label(t["name"])} (in {measured_graph._label(owner_of(t))})"]')
    for owner, target, field in rels:
        if owner["kind"] == SQL:
            lines.append(f'  {idents[id(target)]} ||--o{{ {idents[id(owner)]} : "{measured_graph._label(field)}"')
        else:
            lines.append(f'  {idents[id(owner)]} }}o--|| {idents[id(target)]} : "{measured_graph._label(field)}"')
    return "\n".join(lines)


def diagrams(extract: dict, catalog: list) -> list:
    """[(title, mermaid source, budget)]: one diagram, or one per owner component plus one for the SQL tables."""
    ents = entities(extract)
    roots = measured_graph.package_roots(extract)

    def owner_of(e):
        if e["kind"] == SQL:
            return "SQL tables"
        if catalog:
            return components.component_of(e["path"], catalog)[0] or measured_graph.UNASSIGNED
        return measured_graph.component_area([e["path"]], roots)

    if len(ents) <= MAX_ENTITIES:
        return [("Entities and their relations", _source(ents, ents, owner_of), "")]
    groups: dict = {}
    for e in ents:
        groups.setdefault(owner_of(e), []).append(e)
    ordered = sorted(groups, key=lambda g: (g == "SQL tables", g))
    return [(g, _source(groups[g], ents, owner_of), "" if len(groups[g]) <= MAX_ENTITIES else "area") for g in ordered]


def field_table(cid: str, extract: dict, refs) -> str:
    r = _render()
    rows = []
    for e in entities(extract):
        for f in e.get("fields") or []:
            rows.append([r.E(e["name"]), r.E(f["name"]), r.E(f.get("type") or "-"), r.E(_keys(f) or "-"), r.E(f.get("ref") or "-"),
                         r.path_code(e["path"]), r.source_cell(refs, (e["path"], f.get("line")))])
    return r.render_table(["Entity", "Field", "Type", "Key", "References", "Defined in", "Source"], rows, refs, "t-" + cid.replace(".", "-") + "-fields", plain=True)


def draw(cid, ctx, refs):
    extract = ctx.get("extract") or {}
    if "models" not in extract:
        return None
    if not entities(extract):
        return '<p class="muted">No entities were found.</p>'
    charts = "".join(measured_graph._diagram(t, src, budget) for t, src, budget in diagrams(extract, ctx.get("catalog") or []))
    return charts + measured_tables.heading("Every field") + field_table(cid, extract, refs)
