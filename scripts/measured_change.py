"""Measured cards of report 10 (change and history), drawn from `extract/history.json` alone (D3).

Nothing here reads the capped `facts` lists. Every table lists every row; a card with nothing to list says so.
"""
from __future__ import annotations

import math
from collections import Counter

import components

SCATTER_W, SCATTER_H = 640, 320
PAD_L, PAD_R, PAD_T, PAD_B = 56, 16, 12, 44


def _render():
    import render  # imported late: render imports measured, which imports this module

    return render


def history_items(ctx, kind):
    return [i for i in (ctx.get("extract") or {}).get("history", []) if i.get("kind") == kind]


def has_history(ctx):
    return bool(history_items(ctx, "meta"))


def none_found(text):
    return f'<p class="muted none-found">{_render().E(text)}</p>'


def complexity_of(ctx):
    return {g["path"]: g["complexity"] for g in (ctx.get("extract") or {}).get("graph", []) if g.get("kind") == "module" and "complexity" in g}


def _table(cid, suffix, columns, rows, refs):
    return _render().render_table(columns, rows, refs, "t-" + cid.replace(".", "-") + suffix, plain=True)


def _num(n):
    return (f"{n:,}", n)


# ------------------------------------------------------------------ change.hotspots


def file_rows(ctx):
    """One dict per source file: the history item (or zeros), component, complexity."""
    extract = ctx.get("extract") or {}
    hist = {i["path"]: i for i in history_items(ctx, "file")}
    lines = components.file_lines(ctx.get("facts") or {})
    cx, catalog = complexity_of(ctx), ctx.get("catalog") or []
    rows = []
    for path in components.source_files(ctx.get("tree"), extract):
        h = hist.get(path) or {}
        rows.append({"path": path, "component": components.component_of(path, catalog)[0] if catalog else None,
                     "commits_12m": h.get("commits_12m", 0), "commits": h.get("commits", 0),
                     "lines": h.get("lines") or lines.get(path, 0), "complexity": cx.get(path), "last": h.get("last_changed")})
    rows.sort(key=lambda r: (-r["commits_12m"], -(r["complexity"] if r["complexity"] is not None else -1), r["path"]))
    return rows


def _ticks_log(top):
    out, v = [], 1
    while v <= top:
        out.append(v)
        v *= 10
    return out or [1]


def scatter(rows):
    """An inline SVG at a fixed size: lines (log scale) across, commits in the last 12 months up."""
    E = _render().E
    top_x = max([r["lines"] for r in rows] + [10])
    top_y = max([r["commits_12m"] for r in rows] + [1])
    span_x = math.log10(top_x) or 1
    inner_w, inner_h = SCATTER_W - PAD_L - PAD_R, SCATTER_H - PAD_T - PAD_B
    x = lambda n: PAD_L + inner_w * math.log10(max(n, 1)) / span_x
    y = lambda n: PAD_T + inner_h * (1 - n / top_y)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{SCATTER_W}" height="{SCATTER_H}" viewBox="0 0 {SCATTER_W} {SCATTER_H}" role="img" '
             f'aria-label="Each dot is a source file: lines across on a log scale, commits in the last 12 months up">']
    parts.append(f'<line x1="{PAD_L}" y1="{PAD_T + inner_h}" x2="{PAD_L + inner_w}" y2="{PAD_T + inner_h}" stroke="currentColor" stroke-opacity="0.4"/>')
    parts.append(f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T + inner_h}" stroke="currentColor" stroke-opacity="0.4"/>')
    for t in _ticks_log(top_x):
        parts.append(f'<text x="{x(t):.1f}" y="{PAD_T + inner_h + 16}" font-size="12" text-anchor="middle" fill="currentColor">{t:,}</text>')
    for t in sorted({0, top_y // 2, top_y}):
        parts.append(f'<text x="{PAD_L - 6}" y="{y(t) + 4:.1f}" font-size="12" text-anchor="end" fill="currentColor">{t}</text>')
    parts.append(f'<text x="{PAD_L + inner_w / 2:.0f}" y="{SCATTER_H - 6}" font-size="12" text-anchor="middle" fill="currentColor">Lines in the file (log scale)</text>')
    parts.append(f'<text x="12" y="{PAD_T + inner_h / 2:.0f}" font-size="12" text-anchor="middle" fill="currentColor" transform="rotate(-90 12 {PAD_T + inner_h / 2:.0f})">Commits in 12 months</text>')
    for r in rows:
        parts.append(f'<circle cx="{x(r["lines"]):.1f}" cy="{y(r["commits_12m"]):.1f}" r="4" fill="var(--primary, currentColor)" fill-opacity="0.7" '
                     f'stroke="var(--background, #fff)" stroke-width="1"><title>{E(r["path"])}: {r["commits_12m"]} commits, {r["lines"]} lines</title></circle>')
    parts.append("</svg>")
    return f'<div class="chart-scroll">{"".join(parts)}</div>'


def component_rows(rows, catalog):
    acc = {c["name"]: {"files": 0, "changes": 0, "lines": 0, "complexity": 0} for c in catalog}
    for r in rows:
        if r["component"] in acc:
            a = acc[r["component"]]
            a["files"] += 1
            a["changes"] += r["commits_12m"]
            a["lines"] += r["lines"]
            a["complexity"] += r["complexity"] or 0
    return acc


def hotspots(cid, ctx, refs):
    if not has_history(ctx):
        return None
    rows = file_rows(ctx)
    if not rows:
        return None
    r = _render()
    idle = sum(1 for x in rows if not x["commits_12m"])
    out = [f'<p>Every source file, most changed in the 12 months before this commit first. {idle} of {len(rows)} files did not change in that time.</p>',
           scatter(rows)]
    cells = [[r.path_code(x["path"]), r.E(x["component"] or "-"), _num(x["commits_12m"]), _num(x["commits"]), _num(x["lines"]),
              _num(x["complexity"]) if x["complexity"] is not None else "-", r.E(x["last"] or "-"), r.source_cell(refs, (x["path"], None))] for x in rows]
    out.append(_table(cid, "-files", ["File", "Component", "Commits (12 months)", "Commits (all)", "Lines", "Complexity", "Last changed", "Source"], cells, refs))
    catalog = ctx.get("catalog") or []
    if catalog:
        acc = component_rows(rows, catalog)
        comp = [[r.E(name), _num(a["files"]), _num(a["changes"]), _num(a["lines"]), _num(a["complexity"])] for name, a in sorted(acc.items())]
        out.append(_table(cid, "-components", ["Component", "Files", "File changes (12 months)", "Lines", "Complexity"], comp, refs))
    else:
        out.append(none_found("There is no components catalog yet, so files are not grouped by component."))
    return "".join(out)


DRAWN = {"change.hotspots": hotspots}
