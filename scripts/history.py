"""Read the whole git history once and fold it into per-file, per-pair and per-person figures.

Nothing here is capped. A commit that touches more than `bulk_files` files (an import, a
reformat) credits no file and no pair; it is listed instead.
"""
from __future__ import annotations

import itertools
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Iterator, NamedTuple

import gather

RECENT_DAYS = gather.KNOWLEDGE_RECENT_DAYS


class Commit(NamedTuple):
    sha: str
    name: str
    email: str
    date: str
    parents: tuple
    message: str
    entries: tuple      # (added, deleted, old path or None, path)

    @property
    def subject(self):
        return self.message.strip().split("\n", 1)[0]


class Folded(NamedTuple):
    files: dict         # path -> {"commits", "commits_12m", "lines_changed", "lines_changed_12m", "last_changed", "authors", "shas"}
    pairs: Counter      # (a, b) sorted -> commits that touched both
    people: dict        # id -> {"commits", "commits_12m", "first", "last"}
    bulk: list          # [{"sha", "files", "author", "date", "subject"}]
    author_of: dict     # sha -> id of the author, for every commit seen
    commits: list       # every commit seen, newest first, without file entries


def parse_record(rec: bytes):
    """One record of the log, or None when it is cut short or has no header."""
    head, _, rest = rec.partition(b"\0")
    meta = head.decode("utf-8", "replace").strip("\n").split("\x1f", 5)
    if len(meta) < 6:
        return None
    parsed = gather.parse_commit(rec)
    if parsed is None:
        return None
    sha, name, email, date, entries = parsed
    return Commit(sha, name, email, date, tuple(meta[4].split()), meta[5].rstrip("\n"), tuple(entries))


def parse_log(data: bytes, drop_last: bool = False) -> Iterator[Commit]:
    """Commits in the order given (newest first). With `drop_last`, the final record is left out
    because the output was cut off and that record may be incomplete."""
    recs = [r for r in data.split(b"\x1e") if r.strip()]
    if drop_last and recs:
        recs.pop()
    for r in recs:
        c = parse_record(r)
        if c:
            yield c


def fold(commits, wanted, cid_of, as_of, bulk_files=None) -> Folded:
    """Credit `commits` (newest first) to files, pairs and people. A rename seen now says where older history belongs."""
    bulk_files = gather.BULK_FILES if bulk_files is None else bulk_files
    recent_from = as_of - timedelta(days=RECENT_DAYS)
    alias, files, pairs, people, bulk, author_of, seen = {}, {}, Counter(), {}, [], {}, []
    for c in commits:
        seen.append(c._replace(entries=()))
        cid = cid_of(c.name, c.email)
        if cid is None:
            continue
        author_of[c.sha] = cid
        if len(c.parents) > 1:
            continue
        dt = datetime.fromisoformat(c.date).astimezone(timezone.utc)
        who = people.setdefault(cid, {"commits": 0, "commits_12m": 0, "first": dt, "last": dt})
        who["commits"] += 1
        who["commits_12m"] += dt >= recent_from
        who["first"], who["last"] = min(who["first"], dt), max(who["last"], dt)
        is_bulk = len(c.entries) > bulk_files
        if is_bulk:
            bulk.append({"sha": c.sha, "files": len(c.entries), "author": cid, "date": c.date, "subject": c.subject})
        touched = set()
        for a, d, old, new in c.entries:
            cur = alias.get(new, new)
            if old is not None:
                alias[old] = cur
            if is_bulk or cur not in wanted:
                continue
            f = files.setdefault(cur, {"commits": 0, "commits_12m": 0, "lines_changed": 0, "lines_changed_12m": 0,
                                       "last_changed": None, "authors": Counter(), "shas": []})
            if cur not in touched:
                f["commits"] += 1
                f["commits_12m"] += dt >= recent_from
                f["authors"][cid] += 1
                f["shas"].append(c.sha)
            f["lines_changed"] += a + d
            f["lines_changed_12m"] += (a + d) * (dt >= recent_from)
            if f["last_changed"] is None or dt > f["last_changed"]:
                f["last_changed"] = dt
            touched.add(cur)
        pairs.update(itertools.combinations(sorted(touched), 2))
    return Folded(files, pairs, people, bulk, author_of, seen)
