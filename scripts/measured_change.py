"""Measured cards of report 10 (change and history), drawn from `extract/history.json` alone (D3).

Nothing here reads the capped `facts` lists. Every table lists every row; a card with nothing to list says so.
"""
from __future__ import annotations

from collections import Counter

import components
import gather

HOTSPOT_FILES = ["File", "Component", "Commits", "Lines added", "Lines removed", "Complexity", "Last changed", "Source"]
HOTSPOT_COMPONENTS = ["Component", "Files", "File changes", "Lines added", "Lines removed", "Complexity"]
PERIODS = (("12m", "Past 12 months"), ("all", "All time"))


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


def foot_notes(*lines):
    """The notes at the bottom of a card, muted, with a bullet between them when there is more than one."""
    E = _render().E
    return '<p class="muted card-notes">' + ' <span class="dot" aria-hidden="true">&bull;</span> '.join(f"<span>{E(t)}</span>" for t in lines if t) + "</p>"


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
                     "added_12m": h.get("lines_added_12m"), "deleted_12m": h.get("lines_deleted_12m"),
                     "added": h.get("lines_added"), "deleted": h.get("lines_deleted")})
    rows.sort(key=lambda r: (-r["commits_12m"], -(r["complexity"] if r["complexity"] is not None else -1), r["path"]))
    return rows


def component_rows(rows, catalog, period="12m"):
    """Per component: files, file changes, lines added and removed (None when the history did not count them) and complexity, for one period."""
    suffix = "_12m" if period == "12m" else ""
    commits = "commits_12m" if period == "12m" else "commits"
    acc = {c["name"]: {"files": 0, "changes": 0, "lines": 0, "added": None, "deleted": None, "complexity": 0} for c in catalog}
    for r in rows:
        if r["component"] in acc:
            a = acc[r["component"]]
            a["files"] += 1
            a["changes"] += r[commits]
            a["lines"] += r["lines"]
            if r["added" + suffix] is not None:   # a history read before added and removed lines were counted leaves these unknown
                a["added"] = (a["added"] or 0) + r["added" + suffix]
                a["deleted"] = (a["deleted"] or 0) + (r["deleted" + suffix] or 0)
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


TOP_SHOWN = 15


def _file_table(cid, rows, refs, period):
    r = _render()
    key = "commits_12m" if period == "12m" else "commits"
    sfx = "_12m" if period == "12m" else ""
    ordered = rows if period == "12m" else sorted(rows, key=lambda x: (-x["commits"], x["path"]))
    cells = [[r.path_code(x["path"]), r.E(x["component"] or "-"), _num(x[key]), _churn(x["added" + sfx]), _churn(x["deleted" + sfx]),
              _num(x["complexity"]) if x["complexity"] is not None else "-", r.E(x["last"] or "-"), r.source_cell(refs, (x["path"], None))] for x in ordered]
    html = _table(cid, "-files" if period == "12m" else "-files-all", HOTSPOT_FILES, cells, refs)
    html = html.replace('<table class="table"', '<table class="table hot-files"', 1)
    return _mark_top(html, [x[key] for x in ordered])


def _mark_top(html, counts):
    """Mark the rows of the TOP_SHOWN most changed files that changed at all; the page script hides the other rows until All files is pressed."""
    head, sep, rest = html.partition("<tbody>")
    rows = rest.split("<tr>")
    marked = [rows[0]] + [("<tr class=\"hot-top\">" if i <= TOP_SHOWN and counts[i - 1] else "<tr>") + r for i, r in enumerate(rows[1:], 1)]
    return head + sep + "".join(marked)


def _component_table(cid, rows, catalog, refs, period):
    r = _render()
    acc = component_rows(rows, catalog, period)
    comp = [[r.E(name), _num(a["files"]), _num(a["changes"]), _churn(a["added"]), _churn(a["deleted"]), _num(a["complexity"])] for name, a in sorted(acc.items())]
    return _table(cid, "-components" if period == "12m" else "-components-all", HOTSPOT_COMPONENTS, comp, refs)


def _by_period(make):
    """The same table for each period; the page script shows the one the pressed period button names."""
    return "".join(f'<div data-hotperiod="{v}"{"" if i == 0 else " hidden"}>{make(v)}</div>' for i, (v, _) in enumerate(PERIODS))


def hotspots(cid, ctx, refs):
    if not has_history(ctx):
        return None
    rows = file_rows(ctx)
    if not rows:
        return None
    out = [mode_buttons("hotperiod", "Time period", PERIODS), mode_buttons("hotshow", "Show", (("top", f"Top {TOP_SHOWN}"), ("all", "All files")))]
    catalog = ctx.get("catalog") or []
    files = _by_period(lambda p: _file_table(cid, rows, refs, p))
    if not catalog:
        return "".join(out) + f'<div class="hot-table">{files}</div>' + none_found("There is no components catalog yet, so files are not grouped by component.")
    out.append(mode_buttons("hot", "Show hotspots by", (("files", "File"), ("components", "Component"))))
    out.append(f'<div class="hot-table" data-hot="files">{files}</div>'
               f'<div class="hot-table" data-hot="components" hidden>{_by_period(lambda p: _component_table(cid, rows, catalog, refs, p))}</div>')
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


def cochange(cid, ctx, refs):
    if not has_history(ctx):
        return None
    r = _render()
    meta = history_items(ctx, "meta")[0]
    shown = pair_rows(ctx)
    foot = foot_notes(f"Pairs of files that changed together in at least {COCHANGE_MIN} commits ({len(shown)} of {meta.get('pairs_total', len(shown))} pairs). "
                      f"Commits touching more than {gather.BULK_FILES} files are left out.",
                      "Share is the co-commits as a percentage of the commits of the less-changed file. At 100%, every time "
                      "the less-changed file changed, the other file changed in the same commit.")
    if not shown:
        return none_found(f"No pair of files changed together in {COCHANGE_MIN} or more commits.") + foot
    rows = [[r.path_code(p["a"]), r.path_code(p["b"]), _num(p["co_commits"]), (f'{p["share"]}%', p["share"]), r.E(link),
             r.source_cell(refs, (p["a"], None), (p["b"], None))] for p, link in shown]
    return _table(cid, "", ["A", "B", "Co-commits", "Share", "Linked in code?", "Source"], rows, refs) + foot


# ------------------------------------------------------------------ change.dead-code


def dead_rows(extract, dependencies):
    """[(item, kind, evidence, path or None, line or None)]: tool findings, unused dependencies, modules nothing imports."""
    rows = [(d["name"], d["type"], d["message"] if d.get("confidence") is None else f'{d["message"]} ({d["confidence"]}% confidence)',
             d["path"], d.get("line")) for d in extract.get("dead", [])]
    from_knip = {d["name"] for d in extract.get("dead", []) if d.get("type") == "unused dependency"}  # knip names the same packages
    for u in (dependencies or {}).get("unused", []) or []:
        if u["n"] not in from_knip:
            rows.append((u["n"], "unused dependency", u["note"], None, None))
    graph = extract.get("graph", [])
    imported = {p for g in graph if g.get("kind") == "import" for p in g.get("paths") or []}
    imported |= {p for t in extract.get("tests", []) if t.get("kind") == "test-file" for p in t.get("paths") or []}
    entry_files = {e["path"] for e in extract.get("entry_points", [])}
    for m in sorted((g for g in graph if g.get("kind") == "module"), key=lambda g: g["path"]):
        base = m["path"].rsplit("/", 1)[-1]
        if m.get("language") == "js" or m["path"] in imported or m["path"] in entry_files or base in ("__init__.py", "__main__.py"):
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
    foot = foot_notes("Tool output, not checked by a person: some of these may be used in ways the tools cannot see.")
    if not found:
        return none_found("The tools found nothing unused.") + foot
    rows = [[r.E(item), r.E(kind), r.E(ev), r.source_cell(refs, (path, line)) if path else ""] for item, kind, ev, path, line in found]
    return _table(cid, "", ["Item", "Kind", "Evidence", "Source"], rows, refs) + foot


# ------------------------------------------------------------------ change.in-flight


def in_flight(cid, ctx, refs):
    if not has_history(ctx):
        return None
    r = _render()
    branches = history_items(ctx, "branch")
    notes = ["Compared with the pinned commit. Issue and pull request content is not in the repository and is unknown."]
    if branches and not any(b["remote"] for b in branches):
        notes.append("This repository has no remote branches, so these are local branches.")
    foot = foot_notes(*notes)
    if not branches:
        return none_found("There are no branches other than the default branch.") + foot
    rows = [[r.E(b["ref"]), r.E(f'{b["date"]} {b["sha"][:7]}'), r.E(f'{b["ahead"]} ahead, {b["behind"]} behind'), r.E(b["author"]),
             refs.mark(["commit:" + b["sha"]])] for b in branches]
    return _table(cid, "", ["Branch", "Last commit", "Ahead/behind", "Author", "Source"], rows, refs) + foot


DRAWN = {"change.hotspots": hotspots, "change.cochange": cochange, "change.dead-code": dead_code, "change.in-flight": in_flight}
