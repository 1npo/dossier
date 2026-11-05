"""Read the whole git history once and fold it into per-file, per-pair and per-person figures.

Nothing here is capped. A commit that touches more than `bulk_files` files (an import, a
reformat) credits no file and no pair; it is listed instead.
"""
from __future__ import annotations

import itertools
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
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


def fold(commits, wanted, cid_of, as_of, bulk_files=None, hook=None) -> Folded:
    """Credit `commits` (newest first) to files, pairs and people. A rename seen now says where older history belongs.
    `hook(commit, id, paths)` is called for every non-merge commit with the current paths it touched (none for a bulk commit)."""
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
        if hook:
            hook(c, cid, touched)
    return Folded(files, pairs, people, bulk, author_of, seen)


# --------------------------------------------------------------------------- the output file

LOG_FORMAT = "%x1e%H%x1f%aN%x1f%aE%x1f%aI%x1f%P%x1f%B"
REASON_SHALLOW = "this is a shallow clone"
REASON_STOPPED = "reading the history took too long"
REASON_BLAME = "git blame ran out of time for some files"


def _read(res):
    """The text of a finished child process, then remove its stdout file."""
    try:
        return res.stdout.read_bytes()
    finally:
        res.stdout.unlink(missing_ok=True)


def _git(run, args, timeout, stage="history"):
    res = run(["git", *args], stage=stage, timeout=timeout, profile="tool")
    return res, _read(res)


def _day(dt):
    return dt.date().isoformat() if dt else None


def _assistants(commits_by_label):
    return [{"kind": "assistant", "path": "", "name": label, "commits": v["commits"], "files": dict(sorted(v["files"].items()))}
            for label, v in sorted(commits_by_label.items())]


def collect(top, sha, run, handed, timeout) -> dict:
    """The envelope of `extract/history.json` (D2). `handed` is what `gather.collect` hands over; `run` is a bound `sandbox.run`."""
    as_of = datetime.fromisoformat(handed["as_of"]).astimezone(timezone.utc)
    canon, display, ctype = handed["canon"], handed["display"], handed["ctype"]
    lines, blamed = handed["lines"], handed.get("blamed") or {}
    cid_of = lambda n, e: canon.get(gather.ident_id(n, e)) or gather.ident_id(n, e)
    res, data = _git(run, ["log", sha, "-M", "--numstat", "-z", f"--format={LOG_FORMAT}"], timeout)
    stopped = bool(res.timed_out)
    failed = not stopped and res.returncode not in (0, None)
    commits = [] if failed else list(parse_log(data, drop_last=stopped))
    _, total_raw = _git(run, ["rev-list", "--count", sha], 60)
    total = int(total_raw.strip() or 0) if total_raw.strip().isdigit() else len(commits)
    assisted, labelled = Counter(), {}

    def hook(c, cid, touched):
        marker = gather.AGENT_MSG.search(c.message)
        if not marker or ctype.get(cid, "human") != "human":
            return
        assisted[cid] += 1
        for label, pat in gather.AGENT_LABELS:
            if re.search(pat, marker.group(0), re.I):
                slot = labelled.setdefault(label, {"commits": 0, "files": Counter()})
                slot["commits"] += 1
                slot["files"].update(touched)
                break

    folded = fold(commits, set(lines), cid_of, as_of, hook=hook)
    shallow = bool(handed.get("shallow"))
    blame_total = sum(1 for n in lines.values() if n)
    blame_done = sum(1 for p, n in lines.items() if n and p in blamed)
    reasons = ([REASON_SHALLOW] if shallow else []) + ([REASON_STOPPED] if stopped else []) \
        + ([REASON_BLAME] if blame_done < blame_total else []) \
        + (["git could not read the history"] if failed else [])
    items = [{"kind": "meta", "path": "", "status": "partial" if reasons else "ok", "reasons": reasons,
              "commits_seen": len(commits), "commits_total": total, "shallow": shallow, "stopped_early": stopped,
              "blame_done": blame_done, "blame_total": blame_total, "as_of": _day(as_of),
              "window_from": _day(as_of - timedelta(days=RECENT_DAYS)), "pairs_total": len(folded.pairs),
              "bulk_commits": len(folded.bulk), "owner_rule": "authors", "owner_status": "ok", "owner_reason": None, "prs_found": 0}]
    for path in sorted(folded.files):
        f = folded.files[path]
        authors = dict(f["authors"])
        items.append({"kind": "file", "path": path, "lines": lines.get(path, 0), "commits": f["commits"], "commits_12m": f["commits_12m"],
                      "lines_changed": f["lines_changed"], "lines_changed_12m": f["lines_changed_12m"], "last_changed": _day(f["last_changed"]),
                      "authors": authors, "blame": blamed.get(path), "owners": authors, "owner_lines": blamed.get(path)})
    for (a, b), n in sorted(folded.pairs.items()):
        ca, cb = folded.files[a]["commits"], folded.files[b]["commits"]
        items.append({"kind": "pair", "path": a, "a": a, "b": b, "co_commits": n, "commits_a": ca, "commits_b": cb,
                      "share": round(100 * n / min(ca, cb))})
    for cid in sorted(folded.people):
        p = folded.people[cid]
        items.append({"kind": "person", "path": "", "person": cid, "name": display.get(cid, cid), "type": ctype.get(cid, "human"),
                      "commits": p["commits"], "commits_12m": p["commits_12m"], "assisted": assisted[cid],
                      "first": _day(p["first"]), "last": _day(p["last"]),
                      "aliases": sorted(i for i, best in canon.items() if best == cid and i != cid),
                      "owned_commits": p["commits"], "owned_lines": sum(b.get(cid, 0) for b in blamed.values()), "username": None})
    for b in folded.bulk:
        items.append({"kind": "bulk", "path": "", **{**b, "author": display.get(b["author"], b["author"])}})
    items += _assistants(labelled)
    return {"schema": 1, "sha": sha, "adapters": {"git": {"sha": sha, "version": "1", "tools": {},
            "tool_status": {"git": {"status": "ok" if not failed else "failed", "reason": None if not failed else "git log failed"}}, "items": items}}}


def items_of(data):
    return data["adapters"]["git"]["items"]


def meta_of(data):
    return next(i for i in items_of(data) if i["kind"] == "meta")


def write(out, data) -> None:
    path = Path(out) / "extract" / "history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)
