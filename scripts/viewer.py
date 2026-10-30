"""Choose which cited files to embed in the page for the code viewer, and how much of each.

A file of at most MAX_LINES lines (and MAX_BYTES of text) is embedded whole. A longer one is embedded as the
window that covers the most cited ranges. Citations outside their file's window, and files dropped to keep the
page small, do not open the viewer.
"""
from __future__ import annotations

import html
import json
import sys
from bisect import bisect_right
from itertools import accumulate

try:
    from pygments import lex
    from pygments.lexers import get_lexer_for_filename
    from pygments.token import Comment, Generic, Keyword, Name, Number, Operator, String
    from pygments.util import ClassNotFound
except ImportError:
    lex = None

MAX_LINES = 1500
MAX_BYTES = 150_000
BUDGET = 3_000_000       # bytes of embedded text per page, counted before highlighting (markup adds about 50%)
MINIFIED_LINE = 1000     # a line this long means a minified or generated file
TOKEN_CLASSES = ("c", "k", "s", "m", "nf", "nb", "nt", "na", "no", "gd", "gi", "gh")    # the span classes dossier.css colors
_warned = False


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


def token_class(tt):
    """The short class a token is drawn with, or "" for plain text. Few classes keep the markup small."""
    for cls, family in (("c", Comment), ("k", Keyword), ("s", String), ("m", Number), ("nf", Name.Function), ("nf", Name.Class),
                        ("nb", Name.Builtin), ("nt", Name.Tag), ("na", Name.Attribute), ("nt", Name.Decorator), ("no", Name.Constant),
                        ("k", Operator.Word), ("gd", Generic.Deleted), ("gi", Generic.Inserted), ("gh", Generic.Heading)):
        if tt in family:
            return cls
    return ""


def highlight(path, lines):
    """One HTML string per line: escaped text, with <i class=k> and the like around tokens.
    The whole file is lexed, so a window that starts mid-file still opens in the right state.
    Without Pygments, or for a file type it does not know, the lines are only escaped."""
    global _warned
    plain = [html.escape(l, quote=False) for l in lines]
    if lex is None:
        if not _warned:
            print("warning: Pygments is not installed, so code in the viewer is not highlighted", file=sys.stderr)
            _warned = True
        return plain
    try:
        lexer = get_lexer_for_filename(path, stripnl=False)
    except ClassNotFound:
        return plain
    out, cur = [], []    # cur: the [class, text] runs of the line being built; neighbors of one class become one span
    def flush():
        out.append("".join(f'<i class={c}>{html.escape(t, quote=False)}</i>' if c else html.escape(t, quote=False) for c, t in cur))
        cur.clear()
    for tt, text in lex("\n".join(lines) + "\n", lexer):
        cls = token_class(tt) if text.strip() else ""
        for i, part in enumerate(text.split("\n")):
            if i:
                flush()
            if part:
                if cur and cur[-1][0] == cls:
                    cur[-1][1] += part
                else:
                    cur.append([cls, part])
    flush()
    return out[:len(lines)]


def embed(files, windows):
    """The JSON for the page's code-data block: per path, the file's line count, the window's first line and its lines as HTML."""
    data = {p: {"total": len(files[p]["lines"]), "start": w[0], "lines": highlight(p, files[p]["lines"])[w[0] - 1:w[1]]} for p, w in sorted(windows.items())}
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return text.replace("</", "<\\/").replace("<!--", "<\\u0021--")
