"""Measured cards of report 13 (contributors) drawn from `extract/history.json` alone (D3, D4)."""
from __future__ import annotations

import re

import components
import measured_change


def _render():
    import render  # imported late: render imports measured, which imports this module

    return render


def workflow(cid, ctx, refs):
    """The six fixed rows, in the spec's order."""
    rows = measured_change.history_items(ctx, "workflow")
    if not rows:
        return None
    r = _render()
    cells = [[r.E(w["convention"]), r.E(w["observed"]), r.E(w["evidence"]),
              refs.mark(["commit:" + sha for sha in w.get("commits") or []])] for w in rows]
    return r.render_table(["Convention", "Observed", "Evidence", "Source"], cells, refs, "t-contributors-workflow", plain=True)


def names_of(ctx):
    """Identity (or merged alias) -> display name, from the `person` items."""
    names = {}
    for p in measured_change.history_items(ctx, "person"):
        names[p["person"]] = p["name"]
        for alias in p.get("aliases") or []:
            names.setdefault(alias, p["name"])
    return names


def component_stats(ctx):
    """{component: {"owned": {id: lines}, "lines": {id: lines}, "commits": {id: n}, "files": n, "approx": bool}} from the `file` items.

    `owned` counts lines by the owner of the commit that last changed them, `lines` by author. A file with no blame
    adds its commits only, and its component is marked `approx`. Per-person commits in the last 12 months are not
    kept per file in `extract/history.json`, so there is no such figure here.
    """
    catalog = ctx.get("catalog") or []
    stats = {r["name"]: {"owned": {}, "lines": {}, "commits": {}, "files": 0, "approx": False} for r in catalog}
    for f in measured_change.history_items(ctx, "file"):
        name = components.component_of(f["path"], catalog)[0]
        if name not in stats:
            continue
        s = stats[name]
        s["files"] += 1
        for key, src in (("commits", f.get("authors")), ("lines", f.get("blame")), ("owned", f.get("owner_lines"))):
            for who, n in (src or {}).items():
                s[key][who] = s[key].get(who, 0) + n
        if f.get("blame") is None or f.get("owner_lines") is None:
            s["approx"] = True
    return stats


def bus_factor(ctx):
    """{"bus_factor", "top_owner_share"} over the lines owned by humans. Both are None when no human owns a line."""
    owned = sorted((p.get("owned_lines") or 0 for p in measured_change.history_items(ctx, "person") if p.get("type") == "human"), reverse=True)
    total = sum(owned)
    if not total:
        return {"bus_factor": None, "top_owner_share": None}
    running = 0
    for n, lines in enumerate(owned, 1):
        running += lines
        if 2 * running > total:
            break
    return {"bus_factor": n, "top_owner_share": round(100 * owned[0] / total)}


def _key(text):
    return re.sub(r"\s+", " ", re.sub(r"\[\[.*?\]\]", "", str(text)).replace("`", "")).strip().lower()


def _ids_by_name(ctx):
    found = {}
    for ident, name in names_of(ctx).items():
        found.setdefault(_key(name), set()).add(ident)
    return found


def _fill_rows(entry, columns, fill):
    """A copy of `entry` whose tables holding every column in `columns` have `fill(cells, at)` applied to each row."""
    blocks = []
    for block in entry.get("blocks") or []:
        if isinstance(block, dict) and block.get("type") == "table" and all(c in (block.get("columns") or []) for c in columns):
            at = {c: block["columns"].index(c) for c in block["columns"]}
            rows = []
            for row in block.get("rows") or []:
                cells = list(row["cells"])
                fill(cells, at)
                rows.append({**row, "cells": cells})
            block = {**block, "rows": rows}
        blocks.append(block)
    return {**entry, "blocks": blocks}


def _concentration(entry, ctx):
    stats, ids = component_stats(ctx), _ids_by_name(ctx)
    wanted = {_key(n): n for n in stats}

    def fill(cells, at):
        comp, owner = stats.get(wanted.get(_key(cells[at["Area"]]))), ids.get(_key(cells[at["Owner"]]))
        total = sum(comp["owned"].values()) if comp else 0
        cells[at["Share"]] = f"{round(100 * sum(comp['owned'].get(i, 0) for i in owner) / total)}%" if comp and owner and total else "-"

    return _fill_rows(entry, ("Area", "Owner", "Share"), fill)


def _agents(entry, ctx):
    stats, persons = component_stats(ctx), measured_change.history_items(ctx, "person")
    by_name = {_key(p["name"]): p for p in persons if p.get("type") in ("agent", "bot")}
    assistants = {_key(a["name"]): a for a in measured_change.history_items(ctx, "assistant")}
    total, catalog = sum(p["commits"] for p in persons), ctx.get("catalog") or []

    def areas(counts):
        ranked = sorted((-n, name) for name, n in counts.items() if n)
        return ", ".join(name for _, name in ranked) or "-"

    def fill(cells, at):
        who = _key(cells[at["Identity"]])
        person, helper = by_name.get(who), assistants.get(who)
        if person:
            mine = {person["person"], *(person.get("aliases") or [])}
            counts = {name: sum(n for i, n in s["commits"].items() if i in mine) for name, s in stats.items()}
            commits = person["commits"]
        elif helper:
            counts = {}
            for path, n in (helper.get("files") or {}).items():
                name = components.component_of(path, catalog)[0] if catalog else None
                if name:
                    counts[name] = counts.get(name, 0) + n
            commits = helper["commits"]
        else:
            cells[at["Areas touched"]] = cells[at["Share of commits"]] = "-"
            return
        cells[at["Areas touched"]] = areas(counts)
        cells[at["Share of commits"]] = f"{round(100 * commits / total)}% ({commits} commits)" if total else "-"

    return _fill_rows(entry, ("Identity", "Areas touched", "Share of commits"), fill)


def fill(entry, cid, ctx):
    """The measured cells of Knowledge concentration and Agents and bots. Without history the entry is returned as written."""
    if not measured_change.has_history(ctx):
        return entry
    if cid == "contributors.concentration":
        return _concentration(entry, ctx)
    if cid == "contributors.agents":
        return _agents(entry, ctx)
    return entry


DRAWN = {"contributors.workflow": workflow}
