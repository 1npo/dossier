"""Findings for the change reports that a regex can make: decision markers, TODO counts, decision documents, long commit messages."""
from __future__ import annotations

import re

COMMENT_START = ("#", "//", "--", "/*", "*")
RULES = (("marker.hack", re.compile(r"\bHACK\b")),
         ("marker.xxx", re.compile(r"\bXXX\b")),
         ("marker.workaround", re.compile(r"work[\s-]?around", re.I)),
         ("marker.bug-id", re.compile(r"\b(?:(?:BUG|ISSUE|JIRA)[-#]?\d+|[A-Z]{2,}-\d+)\b")))
TODO = re.compile(r"\b(?:TODO|FIXME)\b")
DECISION_DOC = re.compile(r"(^|/)(adr|adrs|decisions?)/|(^|/)docs/.*(design|architecture|rfc)", re.I)
TRAILER = re.compile(r"^[A-Za-z][A-Za-z-]*:\s")
LONG_LINES = 8
SNIPPET = 160


def is_comment(line: str) -> bool:
    s = line.strip()
    return s.startswith(COMMENT_START) or " # " in s or " // " in s


def scan(path: str, text: str):
    """(marker items, TODO and FIXME count) of one text file. TODO and FIXME are counted, not listed."""
    items, todos = [], 0
    for n, line in enumerate(text.splitlines(), 1):
        if not is_comment(line):
            continue
        todos += len(TODO.findall(line))
        for rule, rx in RULES:
            if rx.search(line):
                items.append({"kind": "marker", "path": path, "line": n, "end_line": n, "rule": rule, "snippet": line.strip()[:SNIPPET]})
    return items, todos


def decision_docs(tree) -> list:
    return sorted(p for p in tree if DECISION_DOC.search(p))


def _body_lines(message: str) -> int:
    lines = message.strip().split("\n")[1:]
    while lines and (not lines[-1].strip() or TRAILER.match(lines[-1])):
        lines.pop()
    return sum(1 for l in lines if l.strip())


def long_commits(commits) -> list:
    """Non-merge commits whose message has at least 8 non-blank lines after the subject, trailers not counted."""
    out = []
    for c in commits:
        if len(c.parents) > 1:
            continue
        n = _body_lines(c.message)
        if n >= LONG_LINES:
            out.append({"kind": "long-commit", "path": "", "sha": c.sha, "subject": c.subject[:100], "lines": n, "files": len(c.entries)})
    return out
