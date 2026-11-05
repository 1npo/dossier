"""Who owns a commit, a file and a line (D4).

A human answers for what they approve, so a commit by an agent or a bot belongs to the human who approved its pull
request. With one human in the whole history, that human owns everything.
"""
from __future__ import annotations

import github_owners

MESSAGES = {"no-slug": "the repository is not on GitHub", "no-login": "gh is not installed or not logged in"}


def owner_of(author, author_type, pr_owner, sole_human):
    """The owner id of one commit. `pr_owner` is the human who approved or merged its pull request, or None."""
    if sole_human is not None:
        return sole_human
    if author_type == "human":
        return author
    return pr_owner or author


def sole_human_of(types):
    """The only human id in `types` ({id: type}), or None when there are none or several."""
    humans = [i for i, t in types.items() if t == "human"]
    return humans[0] if len(humans) == 1 else None


def apply(folded, types, prs):
    """{commit sha: owner id} for every commit seen. `types` is {id: type}; `prs` is {sha: human id or None}."""
    sole = sole_human_of(types)
    return {sha: owner_of(author, types.get(author, "human"), prs.get(sha), sole) for sha, author in folded.author_of.items()}


def pull_requests(folded, types, display, remote, run, cache, timeout):
    """Read approvals for the commits that need them. Returns (prs {sha: human id}, new people {id: login}, usernames {id: login},
    status, reason, found count). Nothing is read unless two or more humans share the history and a non-human authored a commit."""
    humans = {i for i, t in types.items() if t == "human"}
    wanted = [c.sha for c in folded.commits if len(c.parents) <= 1 and types.get(folded.author_of.get(c.sha), "human") != "human"]
    if len(humans) < 2 or not wanted:
        return {}, {}, {}, "ok", None, 0
    slug = github_owners.slug(remote)
    if not slug:
        return {}, {}, {}, "partial", MESSAGES["no-slug"], 0
    samples = {}
    for c in folded.commits:
        who = folded.author_of.get(c.sha)
        if who in humans and who not in samples.values() and len(c.parents) <= 1:
            samples[c.sha] = who
    found = github_owners.lookup(slug, wanted, run, cache, timeout)
    login_of = github_owners.logins(slug, list(samples), run, timeout)
    by_login = {login: samples[sha] for sha, login in login_of.items()}
    prs, new, usernames = {}, {}, {i: login for login, i in by_login.items()}
    for sha, got in found.items():
        login = got["approver"] or got["merged_by"]
        if not login:
            continue
        ident = by_login.get(login)
        if ident is None:
            ident = f"github:{login}"
            new[ident] = login
            usernames[ident] = login
        prs[sha] = ident
    if found.error or found.unread:
        reason = found.error or MESSAGES["no-login"]
        return prs, new, usernames, "partial", reason, len(found)
    return prs, new, usernames, "ok", None, len(found)
