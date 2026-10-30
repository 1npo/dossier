"""Work out which reports an update has to rewrite, so a rebuild does not re-read and re-write everything.

A report is stale when something it cites changed since the last render: a cited file was edited inside the cited
lines, deleted, or lost or gained a neighbour; a cited directory changed; a correction is pending. Citations whose
lines did not move are kept, with their line numbers shifted to the new commit. Everything here is plain git and
JSON, so no model has to read anything to decide.
"""
from __future__ import annotations

import posixpath
import re

from render import INLINE_CITE, parse_cite

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.M)
REPO_WIDE = ("overview", "contributors")   # restate things that move with every commit
AGGREGATE = "gaps"                         # lists the open items of the other reports
MAX_CHANGED = 2000                         # facts.delta keeps no more paths than this


def transform(node, fix, key=None):
    """Copy a report with `fix` applied to every citation in it (`cite` lists and inline [[...]] marks)."""
    if isinstance(node, dict):
        return {k: transform(v, fix, k) for k, v in node.items()}
    if isinstance(node, list):
        if key == "cite":
            return [fix(x.strip()) if isinstance(x, str) else x for x in node]
        return [transform(v, fix) for v in node]
    if isinstance(node, str):
        if key == "cite":
            return fix(node.strip())
        if key == "mermaid":      # `a[[x]]` is a Mermaid shape, not a citation
            return node

        def inline(m):
            body, bar, label = m.group(1).partition("|")
            return "[[" + ", ".join(fix(p.strip()) for p in body.split(", ") if p.strip()) + bar + label + "]]"
        return INLINE_CITE.sub(inline, node)
    return node


def cites_in(rep):
    found = []
    transform(rep, lambda raw: found.append(raw) or raw)
    return list(dict.fromkeys(found))


def parse_hunks(diff):
    return [(int(a), 1 if b is None or b == "" else int(b), int(c), 1 if d is None or d == "" else int(d))
            for a, b, c, d in HUNK.findall(diff)]


def shift_range(x, y, hunks):
    """The cited lines x..y of the old file as (x, y) in the new one, or None if a change touches them."""
    off = 0
    for a, b, _, d in hunks:
        if b == 0:                       # pure insertion after old line a
            if x <= a < y:
                return None
            if a < x:
                off += d
        else:                            # old lines a..a+b-1 were replaced or removed
            if a <= y and a + b - 1 >= x:
                return None
            if a + b - 1 < x:
                off += d - b
    return x + off, y + off


def moved(c, hunks):
    """The citation text for a file citation after the diff, or None when its lines changed."""
    r = shift_range(c["a"], c["b"], hunks)
    if r is None:
        return None
    a, b = r
    return f"{c['path']}:{a}-{b}" if c["b"] != c["a"] else f"{c['path']}:{a}"


def assess(rep, changed, hunks_of, deps_changed=False, allow_shift=True):
    """(reasons the report is stale, {old citation: new citation}) for one report."""
    reasons, shifts = [], {}
    cited_dirs = set()
    cited_files = set()
    for raw in cites_in(rep):
        c = parse_cite(raw)
        if c["kind"] == "facts":
            if c["name"] == "manifests" and deps_changed:
                reasons.append("the dependencies it cites changed")
            continue
        if c["kind"] != "file":
            continue
        p = c["path"].rstrip("/")
        cited_files.add(p)
        cited_dirs.add(posixpath.dirname(p))
        status = changed.get(p)
        if status == "D":
            reasons.append(f"{p} was deleted")
        elif status:
            new = moved(c, hunks_of(p)) if (allow_shift and c["a"]) else None
            if new:
                shifts[raw] = new
            else:
                reasons.append(f"{p} changed" + (" (cited as a whole)" if not c["a"] else ""))
        elif any(q.startswith(p + "/") for q in changed):
            reasons.append(f"files under {p}/ changed")
    for q, status in changed.items():
        if status in ("A", "D") and q not in cited_files and posixpath.dirname(q) in cited_dirs:
            reasons.append(f"{q} was {'added' if status == 'A' else 'removed'} next to files it cites")
    return list(dict.fromkeys(reasons)), shifts


def plan(reports, expected, changed, hunks_of, deps_changed, pending_corrections, commits_added, allow_shift=True):
    """Decide the stale reports.

    reports: {id: report dict} that exist; expected: ids that should exist; changed: {path: status letter};
    pending_corrections: {report id: [correction ids]}.
    Returns {"stale": {id: [reasons]}, "shifts": {id: {old: new}}}.
    """
    stale, shifts = {}, {}
    for rid in expected:
        rep = reports.get(rid)
        if rep is None:
            stale[rid] = ["it has not been written yet"]
            continue
        why, moves = assess(rep, changed, hunks_of, deps_changed, allow_shift)
        if pending_corrections.get(rid):
            why.append("pending correction " + ", ".join(pending_corrections[rid]))
        if rid in REPO_WIDE and commits_added:
            why.append("it summarises the whole repository, which has new commits")
        if why:
            stale[rid] = why
        elif moves:
            shifts[rid] = moves
    if AGGREGATE in expected and AGGREGATE not in stale and any(r != AGGREGATE for r in stale):
        stale[AGGREGATE] = ["it lists the open items of reports that are being rewritten"]
        shifts.pop(AGGREGATE, None)
    return {"stale": stale, "shifts": shifts}


def apply_shifts(rep, moves):
    return transform(rep, lambda raw: moves.get(raw, raw))
