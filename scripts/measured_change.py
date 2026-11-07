"""Measured cards of report 10 (change and history), drawn from `extract/history.json` alone (D3).

Nothing here reads the capped `facts` lists. Every table lists every row; a card with nothing to list says so.
"""
from __future__ import annotations

import math
from collections import Counter

import components
import gather

SCATTER_W, SCATTER_H = 640, 320
HOTSPOT_FILES = ["File", "Component", "Commits (12 months)", "Commits (all)", "Lines", "Lines added (12 months)", "Lines removed (12 months)",
                 "Complexity", "Last changed", "Source"]
HOTSPOT_COMPONENTS = ["Component", "Files", "File changes (12 months)", "Lines", "Lines added (12 months)", "Lines removed (12 months)", "Complexity"]
PAD_L, PAD_R, PAD_T, PAD_B = 56, 16, 12, 44


def _render():
    import render  # imported late: render imports measured, which imports this module

    return render


def history_items(ctx, kind):
    return [i for i in (ctx.get("extract") or {}).get("history", []) if i.get("kind") == kind]


def has_history(ctx):
    return bool(history_items(ctx, "meta"))


def intro(text):
    """The sentence under a card's title: the same muted style on every measured card."""
    return f'<p class="muted">{_render().E(text)}</p>'


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
                     "lines": h.get("lines") or lines.get(path, 0), "complexity": cx.get(path), "last": h.get("last_changed"),
                     "added_12m": h.get("lines_added_12m"), "deleted_12m": h.get("lines_deleted_12m")})
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
    acc = {c["name"]: {"files": 0, "changes": 0, "lines": 0, "added": None, "deleted": None, "complexity": 0} for c in catalog}
    for r in rows:
        if r["component"] in acc:
            a = acc[r["component"]]
            a["files"] += 1
            a["changes"] += r["commits_12m"]
            a["lines"] += r["lines"]
            if r["added_12m"] is not None:   # a history read before added and removed lines were counted leaves these unknown
                a["added"] = (a["added"] or 0) + r["added_12m"]
                a["deleted"] = (a["deleted"] or 0) + (r["deleted_12m"] or 0)
            a["complexity"] += r["complexity"] or 0
    return acc


def _churn(n):
    """A count of lines added or removed in the last 12 months; a dash for a history read before these were counted."""
    return _num(n) if n is not None else ("-", -1)


def mode_buttons(group, label, choices):
    """A labelled button group, the first choice pressed. The page script shows the block marked `data-<group>` equal to the pressed button's value."""
    btns = "".join(f'<button type="button" class="btn" data-variant="outline" data-size="sm" data-{group}-set="{v}" aria-pressed="{"true" if i == 0 else "false"}">{t}</button>'
                   for i, (v, t) in enumerate(choices))
    return (f'<div class="km-ctl mode-ctl"><span class="muted" id="{group}-l">{_render().E(label)}</span>'
            f'<div class="button-group" id="{group}-mode" role="group" aria-labelledby="{group}-l">{btns}</div></div>')


BARS_SHOWN = 15


def bars(rows):
    """The files changed most in the last 12 months as a ranked list of bars, longest first, each with its path and its lines added and removed."""
    E = _render().E
    top = [x for x in rows if x["commits_12m"]][:BARS_SHOWN]
    if not top:
        return none_found("No file changed in the 12 months before this commit.")
    widest = max(x["commits_12m"] for x in top)
    items = []
    for x in top:
        churn = (f'<span class="hb-churn"><span class="hb-add">+{x["added_12m"]:,}</span> <span class="hb-del">&minus;{x["deleted_12m"]:,}</span> lines</span>'
                 if x["added_12m"] is not None else "")
        items.append(f'<li><code class="hb-path" title="{E(x["path"])}">{E(x["path"])}</code>'
                     f'<span class="hb-track"><span class="hb-bar" style="width:{100 * x["commits_12m"] / widest:.1f}%"></span></span>'
                     f'<span class="hb-n">{x["commits_12m"]:,} commits</span>{churn}</li>')
    more = len([x for x in rows if x["commits_12m"]]) - len(top)
    tail = f'<p class="muted">The {len(top)} most changed files{f", of {len(top) + more} that changed" if more else ""}. The table below lists every file.</p>'
    return f'<ol class="hot-bars" aria-label="Files by commits in the last 12 months">{"".join(items)}</ol>{tail}'


def hotspots(cid, ctx, refs):
    if not has_history(ctx):
        return None
    rows = file_rows(ctx)
    if not rows:
        return None
    r = _render()
    idle = sum(1 for x in rows if not x["commits_12m"])
    out = [intro(f'Every source file, most changed in the 12 months before this commit first. {idle} of {len(rows)} files did not change in that time.'),
           mode_buttons("hotchart", "Chart", (("bars", "Ranked bars"), ("scatter", "Scatter"))),
           f'<div data-hotchart="bars">{bars(rows)}</div><div data-hotchart="scatter" hidden>{scatter(rows)}</div>']
    cells = [[r.path_code(x["path"]), r.E(x["component"] or "-"), _num(x["commits_12m"]), _num(x["commits"]), _num(x["lines"]),
              _churn(x["added_12m"]), _churn(x["deleted_12m"]),
              _num(x["complexity"]) if x["complexity"] is not None else "-", r.E(x["last"] or "-"), r.source_cell(refs, (x["path"], None))] for x in rows]
    files = _table(cid, "-files", HOTSPOT_FILES, cells, refs)
    catalog = ctx.get("catalog") or []
    if not catalog:
        return "".join(out) + f'<div class="hot-table">{files}</div>' + none_found("There is no components catalog yet, so files are not grouped by component.")
    acc = component_rows(rows, catalog)
    comp = [[r.E(name), _num(a["files"]), _num(a["changes"]), _num(a["lines"]), _churn(a["added"]), _churn(a["deleted"]), _num(a["complexity"])]
            for name, a in sorted(acc.items())]
    components_ = _table(cid, "-components", HOTSPOT_COMPONENTS, comp, refs)
    out.append(mode_buttons("hot", "Show hotspots by", (("files", "File"), ("components", "Component"))))
    out.append(f'<div class="hot-table" data-hot="files">{files}</div><div class="hot-table" data-hot="components" hidden>{components_}</div>')
    return "".join(out)


# ------------------------------------------------------------------ change.cochange

COCHANGE_MIN = 3


def _covered(extract):
    graph = {g["path"] for g in extract.get("graph", []) if g.get("kind") == "module"}
    return graph | {t["path"] for t in extract.get("tests", []) if t.get("kind") == "test-file"}


def linked(a, b, extract) -> str:
    """`yes` when an import, a reference edge or a test's imports join the two files, `no` when both are covered and nothing does,
    `not in the graph` when either is not covered."""
    covered = _covered(extract)
    if a not in covered or b not in covered:
        return "not in the graph"
    edges = [(g["path"], p) for g in extract.get("graph", []) if g.get("kind") == "import" for p in g.get("paths") or []]
    edges += [(g["path"], p) for g in extract.get("symbols", []) if g.get("kind") == "ref-edge" for p in g.get("paths") or []]
    edges += [(t["path"], p) for t in extract.get("tests", []) if t.get("kind") == "test-file" for p in t.get("paths") or []]
    return "yes" if (a, b) in edges or (b, a) in edges else "no"


def pair_rows(ctx):
    extract = ctx.get("extract") or {}
    pairs = [p for p in history_items(ctx, "pair") if p["co_commits"] >= COCHANGE_MIN]
    pairs.sort(key=lambda p: (-p["co_commits"], -p["share"], p["a"], p["b"]))
    return [(p, linked(p["a"], p["b"], extract)) for p in pairs]


CLUSTER_SHARE, CLUSTER_MIN_FILES, CLUSTER_LINKED = 50, 3, 60
CLUSTER_COLUMNS = ["Files", "Size", "Typical share", "Pairs that co-changed", "Linked in code?", "Source"]


def clusters(ctx):
    """Groups of at least CLUSTER_MIN_FILES files that change together, largest first. Each is {"files", "edges": [(pair, link)]}.

    A pair counts when its share is CLUSTER_SHARE percent or more. A group grows from the strongest pair left: a file joins when it changes with at
    least CLUSTER_LINKED percent of the files already in it. Following pairs one after another instead would chain unrelated files into one big
    group. A file belongs to one group."""
    edge = {}
    for p, link in pair_rows(ctx):
        if p["share"] >= CLUSTER_SHARE:
            edge[(p["a"], p["b"])] = edge[(p["b"], p["a"])] = (p, link)
    order = sorted({v[0]["a"] + "\0" + v[0]["b"]: v for v in edge.values()}.values(), key=lambda v: (-v[0]["share"], -v[0]["co_commits"], v[0]["a"], v[0]["b"]))
    free, out = {f for pair in edge for f in pair}, []
    for seed, _ in order:
        if seed["a"] not in free or seed["b"] not in free:
            continue
        group = [seed["a"], seed["b"]]
        while True:
            fit = []
            for f in free - set(group):
                links = [edge[(f, g)][0]["share"] for g in group if (f, g) in edge]
                if links and 100 * len(links) >= CLUSTER_LINKED * len(group):
                    fit.append((-len(links), -sum(links), f))
            if not fit:
                break
            group.append(min(fit)[2])
        if len(group) >= CLUSTER_MIN_FILES:
            free -= set(group)
            found = [edge[(g, h)] for i, g in enumerate(group) for h in group[i + 1:] if (g, h) in edge]
            out.append({"files": sorted(group), "edges": found})
    out.sort(key=lambda c: (-len(c["files"]), -sum(p["share"] for p, _ in c["edges"]) / len(c["edges"]), c["files"][0]))
    return out


def cluster_rows(found, refs):
    r = _render()
    rows = []
    for c in found:
        n, e = len(c["files"]), len(c["edges"])
        possible = n * (n - 1) // 2
        typical = round(sum(p["share"] for p, _ in c["edges"]) / e)
        yes = sum(1 for _, k in c["edges"] if k == "yes")
        link = f"none of the {e} pairs" if not yes else f"all {e} pairs" if yes == e else f"{yes} of the {e} pairs"
        listing = "<br>".join(r.path_code(f) for f in c["files"])
        rows.append([listing, _num(n), (f"{typical}%", typical), (f"{e} of {possible}", e / possible), r.E(link),
                     r.source_cell(refs, *[(f, None) for f in c["files"]])])
    return rows


def cochange(cid, ctx, refs):
    if not has_history(ctx):
        return None
    r = _render()
    meta = history_items(ctx, "meta")[0]
    shown = pair_rows(ctx)
    lead = (f'<p class="muted">Pairs of files that changed together in at least {COCHANGE_MIN} commits ({len(shown)} of {meta.get("pairs_total", len(shown))} pairs). '
            f'Commits touching more than {gather.BULK_FILES} files are left out.</p>')
    foot = ('<p class="muted cochange-note">Share is the co-commits as a percentage of the commits of the less-changed file. At 100%, every time '
            'the less-changed file changed, the other file changed in the same commit.</p>')
    if not shown:
        return lead + none_found(f"No pair of files changed together in {COCHANGE_MIN} or more commits.") + foot
    rows = [[r.path_code(p["a"]), r.path_code(p["b"]), _num(p["co_commits"]), (f'{p["share"]}%', p["share"]), r.E(link),
             r.source_cell(refs, (p["a"], None), (p["b"], None))] for p, link in shown]
    pairs_view = _table(cid, "", ["A", "B", "Co-commits", "Share", "Linked in code?", "Source"], rows, refs)
    found = clusters(ctx)
    note = (f'<p class="muted">A change cluster is a group of {CLUSTER_MIN_FILES} or more files in which every file changes with at least {CLUSTER_LINKED}% of the others, '
            f'counting only pairs with a share of {CLUSTER_SHARE}% or more. "Pairs that co-changed" is how many of the possible pairs in the group qualify. '
            'Linked in code counts those pairs that an import, a call or a test also joins: pairs with no link are the hidden coupling.</p>')
    cluster_view = (note + (_table(cid, "-clusters", CLUSTER_COLUMNS, cluster_rows(found, refs), refs) if found else
                    none_found(f"No group of {CLUSTER_MIN_FILES} or more files changes together closely enough to form a cluster.")))
    return (lead + mode_buttons("cc", "Show co-changes as", (("pairs", "Pairs"), ("clusters", "Change clusters")))
            + f'<div data-cc="pairs">{pairs_view}</div><div data-cc="clusters" hidden>{cluster_view}</div>' + foot)


# ------------------------------------------------------------------ change.dead-code


def dead_rows(extract, dependencies):
    """[(item, kind, evidence, path or None, line or None)]: tool findings, unused dependencies, modules nothing imports."""
    rows = [(d["name"], d["type"], f'{d["message"]} ({d["confidence"]}% confidence)', d["path"], d.get("line")) for d in extract.get("dead", [])]
    for u in (dependencies or {}).get("unused", []) or []:
        rows.append((u["n"], "unused dependency", u["note"], None, None))
    graph = extract.get("graph", [])
    imported = {p for g in graph if g.get("kind") == "import" for p in g.get("paths") or []}
    imported |= {p for t in extract.get("tests", []) if t.get("kind") == "test-file" for p in t.get("paths") or []}
    entry_files = {e["path"] for e in extract.get("entry_points", [])}
    for m in sorted((g for g in graph if g.get("kind") == "module"), key=lambda g: g["path"]):
        base = m["path"].rsplit("/", 1)[-1]
        if m["path"] in imported or m["path"] in entry_files or base in ("__init__.py", "__main__.py"):
            continue
        rows.append((m["module"], "module nothing imports", "No module and no test imports it.", m["path"], None))
    return rows


def dead_code(cid, ctx, refs):
    extract = ctx.get("extract") or {}
    if "dead" not in extract and "graph" not in extract:
        return None
    r = _render()
    deps = (ctx.get("facts") or {}).get("dependencies")
    found = dead_rows(extract, deps)
    lead = intro("Tool output, not checked by a person: some of these may be used in ways the tools cannot see.")
    if not found:
        return lead + none_found("The tools found nothing unused.")
    rows = [[r.E(item), r.E(kind), r.E(ev), r.source_cell(refs, (path, line)) if path else ""] for item, kind, ev, path, line in found]
    return lead + _table(cid, "", ["Item", "Kind", "Evidence", "Source"], rows, refs)


# ------------------------------------------------------------------ change.in-flight


def in_flight(cid, ctx, refs):
    if not has_history(ctx):
        return None
    r = _render()
    branches = history_items(ctx, "branch")
    lead = intro("Compared with the pinned commit. Issue and pull request content is not in the repository and is unknown.")
    if not branches:
        return lead + none_found("There are no branches other than the default branch.")
    if not any(b["remote"] for b in branches):
        lead += intro("This repository has no remote branches, so these are local branches.")
    rows = [[r.E(b["ref"]), r.E(f'{b["date"]} {b["sha"][:7]}'), r.E(f'{b["ahead"]} ahead, {b["behind"]} behind'), r.E(b["author"]),
             refs.mark(["commit:" + b["sha"]])] for b in branches]
    return lead + _table(cid, "", ["Branch", "Last commit", "Ahead/behind", "Author", "Source"], rows, refs)


DRAWN = {"change.hotspots": hotspots, "change.cochange": cochange, "change.dead-code": dead_code, "change.in-flight": in_flight}
