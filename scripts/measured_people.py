"""Measured cards of report 13 (contributors) drawn from `extract/history.json` alone (D3, D4)."""
from __future__ import annotations

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


DRAWN = {"contributors.workflow": workflow}
