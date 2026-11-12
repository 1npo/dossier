"""People figures from `extract/history.json`: display names, per-component ownership and the bus factor.

Pure data, no HTML: the contributors cards (render.measured.people), the summary and the history candidates
all read them from here.
"""
from __future__ import annotations

from dossier.findings import components

__all__ = ["bus_factor", "component_stats", "history_items", "names_of"]


def history_items(ctx, kind):
    return [i for i in (ctx.get("extract") or {}).get("history", []) if i.get("kind") == kind]


def names_of(ctx):
    """Identity (or merged alias) -> display name, from the `person` items."""
    names = {}
    for p in history_items(ctx, "person"):
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
    for f in history_items(ctx, "file"):
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
    owned = sorted((p.get("owned_lines") or 0 for p in history_items(ctx, "person") if p.get("type") == "human"), reverse=True)
    total = sum(owned)
    if not total:
        return {"bus_factor": None, "top_owner_share": None}
    running = 0
    for n, lines in enumerate(owned, 1):
        running += lines
        if 2 * running > total:
            break
    return {"bus_factor": n, "top_owner_share": round(100 * owned[0] / total)}
