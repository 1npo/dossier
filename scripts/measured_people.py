"""Measured cards of report 13 (contributors) drawn from `extract/history.json` alone (D3, D4)."""
from __future__ import annotations

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


DRAWN = {"contributors.workflow": workflow}
