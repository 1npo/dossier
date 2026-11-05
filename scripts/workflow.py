"""The team workflow, measured from git alone: six fixed rows, plus the branches in flight.

Pull requests and reviews live on the hosting service, so two rows are stand-ins and say so.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter
from datetime import date

import gather

CONVENTIONAL = re.compile(r"^(feat|fix|docs|chore|refactor|test|build|ci|perf|style)(\(.+\))?!?: ")
MERGE_BRANCH = [re.compile(r"^Merge (?:remote-tracking )?branch '([^']+)'"), re.compile(r"^Merge pull request #\d+ from [^/\s]+/(\S+)"),
                re.compile(r"^merged\s+(\S+)", re.I)]
SQUASH = re.compile(r"\(#\d+\)\s*$")
REVIEWED = re.compile(r"^(Reviewed-by|Approved-by):", re.I | re.M)
ROWS = ("branch naming and strategy", "merge style", "commit message style", "typical PR size", "review rate", "release cadence")
STAND_IN = "Git does not record pull requests, so this is a stand-in."


def git(run, args, timeout, stage="history"):
    """Run git through the safe runner. Returns (result, stdout bytes); the stdout file is removed."""
    res = run(["git", *args], stage=stage, timeout=timeout, profile="tool")
    try:
        return res, res.stdout.read_bytes()
    finally:
        res.stdout.unlink(missing_ok=True)


def _median(values):
    return round(statistics.median(values)) if values else 0


def branch_name(subject):
    for rx in MERGE_BRANCH:
        m = rx.match(subject)
        if m:
            return m.group(1)
    return None


def _row(convention, observed, evidence, commits=()):
    return {"kind": "workflow", "path": "", "convention": convention, "observed": observed, "evidence": evidence, "commits": list(commits)[:3]}


def rows(commits, merge_sizes, tags, default_branch) -> list:
    """The six rows in the spec's order. `commits` is newest first; `tags` is [(name, ISO day)] oldest first."""
    merges = [c for c in commits if len(c.parents) > 1]
    plain = [c for c in commits if len(c.parents) <= 1]
    named = [(c, branch_name(c.subject)) for c in commits]
    named = [(c, n) for c, n in named if n]
    prefixes = Counter(n.split("/")[0] for _, n in named)
    top = ", ".join(f"{p} ({n})" for p, n in prefixes.most_common(5))
    seen = f"Default branch {default_branch}. " + (f"Most common prefixes: {top}." if top else "No branch names are recorded in merge commits.")
    r1 = _row(ROWS[0], seen, f"{len(named)} merge commits name a branch.", [c.sha for c, _ in named])

    squash = [c for c in plain if SQUASH.search(c.subject)]
    n = len(commits)
    if n and len(merges) / n > 0.10:
        style = "merge commits"
    elif n and len(squash) / n > 0.50:
        style = "squash merges"
    else:
        style = "linear history"
    r2 = _row(ROWS[1], style, f"{len(merges)} merge commits in {n} commits; {len(squash)} subjects end in a pull request number.",
              [c.sha for c in (merges if style == "merge commits" else squash)])

    conv = [c for c in plain if CONVENTIONAL.match(c.subject)]
    style3 = "Conventional commits" if plain and len(conv) / len(plain) > 0.50 else "Free-form sentences"
    r3 = _row(ROWS[2], style3, f"{len(conv)} of {len(plain)} subjects follow the pattern; the median subject is {_median([len(c.subject) for c in plain])} characters.",
              [c.sha for c in conv])

    sized = [merge_sizes[c.sha] for c in merges if c.sha in merge_sizes]
    if merges:
        r4 = _row(ROWS[3], f"About {_median([f for f, _ in sized])} files and {_median([l for _, l in sized])} changed lines per merge (median).",
                  f"Measured on {len(sized)} merge commits against their first parent. {STAND_IN}", [c.sha for c in merges])
    else:
        r4 = _row(ROWS[3], "No merge commits to measure.", STAND_IN)

    reviewed = [c for c in merges if REVIEWED.search(c.message)]
    if merges:
        r5 = _row(ROWS[4], f"{len(reviewed)} of {len(merges)} merge commits carry a Reviewed-by or Approved-by line.",
                  "Reviews held on a hosting service leave no trace in git, so this may be low.", [c.sha for c in reviewed])
    else:
        r5 = _row(ROWS[4], "No merge commits to measure.", "Reviews held on a hosting service leave no trace in git.")

    if not tags:
        r6 = _row(ROWS[5], "No tags at this commit.", "-")
    elif len(tags) == 1:
        r6 = _row(ROWS[5], "One tag.", f"Newest tag {tags[0][0]} on {tags[0][1]}.")
    else:
        days = [(date.fromisoformat(b[1]) - date.fromisoformat(a[1])).days for a, b in zip(tags, tags[1:])]
        r6 = _row(ROWS[5], f"{len(tags)} tags; a median of {_median(days)} days apart.", f"Newest tag {tags[-1][0]} on {tags[-1][1]}.")
    return [r1, r2, r3, r4, r5, r6]


def merge_sizes(top, sha, run, timeout=600) -> dict:
    """{merge sha: (files, changed lines)} against the first parent."""
    _, data = git(run, ["log", sha, "--merges", "--diff-merges=first-parent", "--numstat", "-z", "--format=%x1e%H"], timeout)
    sizes = {}
    for rec in data.split(b"\x1e"):
        head, _, rest = rec.partition(b"\0")
        merge = head.decode("utf-8", "replace").strip()
        if not merge:
            continue
        entries = gather.parse_numstat(rest)
        sizes[merge] = (len(entries), sum(a + d for a, d, _, _ in entries))
    return sizes


def tags(top, sha, run, timeout=60) -> list:
    """[(name, ISO day)] of tags reachable from `sha`, oldest first."""
    _, data = git(run, ["tag", "--merged", sha, "--sort=creatordate", "--format=%(refname:short)\x1f%(creatordate:short)"], timeout)
    out = []
    for line in data.decode("utf-8", "replace").splitlines():
        if "\x1f" in line:
            name, day = line.split("\x1f")
            out.append((name, day))
    return out


def default_branch(top, sha, run, timeout=60) -> str:
    res, data = git(run, ["symbolic-ref", "--short", "-q", "refs/remotes/origin/HEAD"], timeout)
    name = data.decode().strip()
    if res.returncode == 0 and name:
        return name.split("/", 1)[-1]
    _, heads = git(run, ["for-each-ref", "refs/heads", "--format=%(refname:short)"], timeout)
    names = heads.decode().split()
    for guess in ("main", "master"):
        if guess in names:
            return guess
    _, cur = git(run, ["symbolic-ref", "--short", "-q", "HEAD"], timeout)
    return cur.decode().strip() or "(detached HEAD)"


def branches(top, sha, run, default="main", timeout=300) -> list:
    """Remote branches other than HEAD and the default branch, with how far each is ahead of and behind `sha`.
    Local branches are listed only when the repository has no remote ones."""
    fmt = "%(refname)\x1f%(objectname)\x1f%(committerdate:short)\x1f%(authorname)"
    refs = []
    for prefix, remote in (("refs/remotes", True), ("refs/heads", False)):
        _, data = git(run, ["for-each-ref", prefix, f"--format={fmt}"], timeout)
        for line in data.decode("utf-8", "replace").splitlines():
            ref, obj, day, author = (line.split("\x1f") + ["", "", "", ""])[:4]
            short = ref.removeprefix("refs/remotes/").removeprefix("refs/heads/")
            bare = short.split("/", 1)[-1] if remote else short
            if (remote and short.endswith("/HEAD")) or bare == default:
                continue
            refs.append((short, obj, day, author, remote))
        if refs:
            break
    out = []
    for short, obj, day, author, remote in sorted(refs):
        _, counts = git(run, ["rev-list", "--left-right", "--count", f"{sha}...{obj}"], timeout)
        behind, ahead = (int(x) for x in (counts.decode().split() + ["0", "0"])[:2])
        out.append({"kind": "branch", "path": "", "ref": short, "sha": obj, "date": day, "ahead": ahead, "behind": behind,
                    "author": author, "remote": remote})
    return out
