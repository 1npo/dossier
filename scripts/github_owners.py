"""Pull request approvals, read with `gh` (D17). Optional: any failure leaves the commits unread and the caller falls back.

Only the approver, the merger and the commit author's login are read. Other pull request content stays out of reach.
"""
from __future__ import annotations

import json
import re
import time

import gather

BATCH = 50
SHA = re.compile(r"[0-9a-f]{40}")
PR_FIELDS = ("associatedPullRequests(first:5){nodes{number merged mergedBy{login __typename} "
             "reviews(states:APPROVED,last:20){nodes{author{login __typename}}}}}")


class Found(dict):
    """{sha: {"number", "approver", "merged_by"}} for commits that belong to a merged pull request."""
    error: str | None = None
    unread: list


def slug(remote) -> str | None:
    """`owner/name` of a GitHub remote, or None for any other host. `remote` is the `facts.repo.remote` dict or a URL."""
    base = remote.get("web_base") if isinstance(remote, dict) else remote
    m = re.match(r"^https?://github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", base or "")
    return f"{m.group(1)}/{m.group(2)}" if m else None


def _query(owner, name, shas, body):
    parts = " ".join(f'c{i}:object(expression:"{s}"){{... on Commit{{{body}}}}}' for i, s in enumerate(shas))
    return f'{{repository(owner:"{owner}",name:"{name}"){{{parts}}}}}'


def _ask(slug_, shas, body, run, timeout):
    owner, name = slug_.split("/", 1)
    query = _query(owner, name, shas, body)
    res = run(["gh", "api", "graphql", "-f", f"query={query}"], stage="github", timeout=timeout, profile="github")
    try:
        text = res.stdout.read_text(encoding="utf-8", errors="replace")
        err = res.stderr.read_text(encoding="utf-8", errors="replace").strip()
    finally:
        res.stdout.unlink(missing_ok=True)
        res.stderr.unlink(missing_ok=True)
    if res.timed_out:
        raise TimeoutError("gh took too long")
    if res.returncode:
        raise RuntimeError(err.splitlines()[-1][:200] if err else f"gh exited with {res.returncode}")
    try:
        repo = json.loads(text)["data"]["repository"]
    except (ValueError, KeyError, TypeError):
        raise RuntimeError("gh returned something that was not a repository answer") from None
    return {s: (repo or {}).get(f"c{i}") for i, s in enumerate(shas)}


def _person(node):
    """A login for a node of type User that is not classed as a bot or an agent, else None."""
    if not node or node.get("__typename") != "User" or not node.get("login"):
        return None
    return node["login"] if gather.ident_type(node["login"], node["login"]) == "human" else None


def read_commit(node):
    """The pull request owner of one commit's answer, or None when no merged pull request holds it."""
    prs = [p for p in ((node or {}).get("associatedPullRequests") or {}).get("nodes") or [] if p and p.get("merged")]
    if not prs:
        return None
    pr = min(prs, key=lambda p: p["number"])
    approver = None
    for review in (pr.get("reviews") or {}).get("nodes") or []:
        approver = _person(review.get("author")) or approver
    return {"number": pr["number"], "approver": approver, "merged_by": _person(pr.get("mergedBy"))}


def lookup(slug_, shas, run, cache, timeout) -> Found:
    """Pull request owners for `shas`. `cache` ({sha: result}) is read first and filled with new results. Finished batches are kept
    when a later one fails or the time runs out; the commits left unread are in `.unread`."""
    deadline = time.monotonic() + timeout
    found = Found()
    found.unread = []
    todo = []
    for s in shas:
        if s in cache:
            found[s] = cache[s]
        else:
            todo.append(s)
    for i in range(0, len(todo), BATCH):
        batch = [s for s in todo[i:i + BATCH] if SHA.fullmatch(s)]
        if not batch:
            continue
        left = deadline - time.monotonic()
        if left <= 0:
            found.error = "the time for reading pull requests ran out"
        else:
            try:
                answers = _ask(slug_, batch, "author{user{login}} " + PR_FIELDS, run, left)
            except (RuntimeError, TimeoutError) as e:
                found.error = str(e)
        if found.error:
            found.unread = todo[i:]
            break
        for s, node in answers.items():
            got = read_commit(node)
            if got:
                found[s] = cache[s] = got
    return found


def logins(slug_, samples, run, timeout) -> dict:
    """{sha: GitHub login of the commit's author} for the given commits. Commits that fail to resolve are left out."""
    deadline = time.monotonic() + timeout
    out, shas = {}, [s for s in samples if SHA.fullmatch(s)]
    for i in range(0, len(shas), BATCH):
        left = deadline - time.monotonic()
        if left <= 0:
            break
        try:
            answers = _ask(slug_, shas[i:i + BATCH], "author{user{login}}", run, left)
        except (RuntimeError, TimeoutError):
            break
        for s, node in answers.items():
            login = (((node or {}).get("author") or {}).get("user") or {}).get("login")
            if login:
                out[s] = login
    return out
