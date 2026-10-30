"""Choose which cited files to embed in the page for the code viewer, and how much of each.

A file of at most MAX_LINES lines (and MAX_BYTES of text) is embedded whole. A longer one is embedded as the
window that covers the most cited ranges. Citations outside their file's window, and files dropped to keep the
page small, do not open the viewer.
"""
from __future__ import annotations

import json
from bisect import bisect_right
from itertools import accumulate

MAX_LINES = 1500
MAX_BYTES = 150_000
BUDGET = 4_000_000       # bytes of embedded text per page
MINIFIED_LINE = 1000     # a line this long means a minified or generated file


def split_lines(data):
    """Lines of a blob, counted the way Cites.check counts them."""
    lines = data.decode("utf-8", "replace").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [l.removesuffix("\r") for l in lines]


def clip(a, b):
    """The part of a cited range the viewer can show: a range longer than MAX_LINES is cut to its first MAX_LINES."""
    return a, min(b, a + MAX_LINES - 1)


def size_of(lines):
    return sum(len(l.encode("utf-8")) + 1 for l in lines)


def pick_window(lines, ranges):
    """(first, last) line numbers (1-based, inclusive) of the window to embed for a file.
    `ranges` are the file's cited (a, b) ranges, or None for a citation without line numbers."""
    n = len(lines)
    sums = [0] + list(accumulate(len(l.encode("utf-8")) + 1 for l in lines))   # sums[i]: bytes of the first i lines
    numbered = sorted({clip(*r) for r in ranges if r})

    def fit(s):    # the longest window that starts at line s and respects both caps
        e = min(n, s + MAX_LINES - 1)
        return min(e, bisect_right(sums, sums[s - 1] + MAX_BYTES) - 1)

    best = None
    for s in sorted({1} | {a for a, _ in numbered}):
        e = fit(s)
        covered = sum(1 for a, b in numbered if s <= a and b <= e)
        if best is None or covered > best[0]:    # strictly more: ties keep the earliest start
            best = (covered, s, e)
    return best[1], best[2]


def covers(window, r):
    """True when a citation's range (or None, for no line numbers) can be shown in the window."""
    if r is None:
        return True
    a, b = clip(*r)
    return window[0] <= a and b <= window[1]


def plan(files, budget=BUDGET):
    """Decide what to embed. `files` maps path -> {"lines": [...], "ranges": [(a, b) | None, ...]}.
    Returns (windows, dropped): windows maps path -> (first, last); dropped lists the paths cut for size."""
    windows = {p: pick_window(f["lines"], f["ranges"]) for p, f in files.items()}
    cost = {p: size_of(files[p]["lines"][w[0] - 1:w[1]]) for p, w in windows.items()}

    def drop_order(p):    # unnumbered-only files first, then the least cited, then the biggest
        r = set(files[p]["ranges"])
        return (any(r), len(r), -cost[p], p)

    dropped = []
    for p in sorted(windows, key=drop_order):
        if sum(cost.values()) <= budget:
            break
        dropped.append(p)
        del cost[p]
    for p in dropped:
        del windows[p]
    return windows, dropped


def embed(files, windows):
    """The JSON for the page's code-data block: per path, the file's line count, the window's first line and its lines."""
    data = {p: {"total": len(files[p]["lines"]), "start": w[0], "lines": files[p]["lines"][w[0] - 1:w[1]]} for p, w in sorted(windows.items())}
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return text.replace("</", "<\\/").replace("<!--", "<\\u0021--")
