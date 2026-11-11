"""Build a page that holds every M3 card, for the V11 and V12 tests (plan 009, M3-14).

  make(tmp) -> Path to the rendered page

It commits the small repository `tests/fixtures/pyrepo`, runs `prepare` on it, adds extractor output made from its file list plus
generated paths (so the tables are far taller than 40 rows), adds the reports whose cards Claude would write (all "not applicable"), and
renders. The numbers are made up but fixed.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL / "scripts"))

import components  # noqa: E402

PYREPO = SKILL / "tests" / "fixtures" / "pyrepo"
TOP = None  # the committed copy of pyrepo; set by make()
GENERATED = 600  # extra source paths, so the hotspot and blast-radius tables are taller than 40 rows
SCRIPT = SKILL / "scripts" / "dossier.py"
NA_CARDS = {"change": ("change.unfinished", "change.decisions", "change.docs-drift"),
            "contributors": ("contributors.people", "contributors.ask", "contributors.concentration", "contributors.agents", "contributors.doubts")}


def envelope(sha, adapter, items):
    return {"schema": 1, "sha": sha, "adapters": {adapter: {"sha": sha, "version": "1", "tools": {}, "tool_status": {}, "items": items}}}


def commit_pyrepo(dest: Path) -> Path:
    """Copy tests/fixtures/pyrepo to dest/pyrepo and commit it once on main; return the repository path."""
    repo = Path(dest) / "pyrepo"
    shutil.copytree(PYREPO, repo, ignore=shutil.ignore_patterns("__pycache__"))
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull, "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@x.io",
           "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@x.io"}
    for args in (("init", "-b", "main"), ("add", "-A"), ("commit", "-m", "fixture")):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)
    return repo


def tree_at(sha):
    out = subprocess.run(["git", "-C", str(TOP), "ls-tree", "-r", "--name-only", sha], capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line]


def history_items(source, people):
    items = [{"kind": "meta", "path": "", "status": "ok", "reasons": [], "commits_seen": 300, "commits_total": 300, "shallow": False, "stopped_early": False,
              "blame_done": len(source), "blame_total": len(source), "as_of": "2026-10-31", "window_from": "2025-10-31", "pairs_total": 0,
              "bulk_commits": 0, "owner_rule": "authors", "owner_status": "ok", "owner_reason": None, "prs_found": 0}]
    for i, p in enumerate(source):
        c12 = (i * 7) % 11
        items.append({"kind": "file", "path": p, "lines": 10 + (i * 37) % 900, "commits": c12 + i % 5, "commits_12m": c12, "lines_changed": 40 * c12,
                      "lines_changed_12m": 30 * c12, "last_changed": "2026-10-%02d" % (1 + i % 28), "authors": {people[0]: 1}, "blame": {people[0]: 10},
                      "owners": {people[0]: 1}, "owner_lines": {people[0]: 10}})
    pairs = [(source[i], source[i + 1], 3 + i % 5) for i in range(0, min(len(source) - 1, 40))]
    for a, b, n in pairs:
        items.append({"kind": "pair", "path": a, "a": a, "b": b, "co_commits": n, "commits_a": 9, "commits_b": 8, "share": round(100 * n / 8)})
    items.append({"kind": "pair", "path": source[0], "a": source[0], "b": source[2], "co_commits": 1, "commits_a": 9, "commits_b": 8, "share": 12})
    for cid, kind in zip(people, ("human", "human", "agent")):
        items.append({"kind": "person", "path": "", "person": cid, "name": cid.split("@")[0].title(), "type": kind, "commits": 50, "commits_12m": 20,
                      "assisted": 0, "first": "2025-01-01", "last": "2026-10-30", "aliases": [], "owned_commits": 50, "owned_lines": 100, "username": None})
    for n, (ref, remote) in enumerate((("origin/feat-a", True), ("origin/fix-b", True))):
        items.append({"kind": "branch", "path": "", "ref": ref, "sha": f"{n + 1:040x}", "date": "2026-10-20", "ahead": n + 2, "behind": 3, "author": "Ann", "remote": remote})
    rows = (("branch naming and strategy", "Default branch main. Most common prefixes: feat (3).", "3 merge commits name a branch."),
            ("merge style", "merge commits", "30 merge commits in 300 commits; 0 subjects end in a pull request number."),
            ("commit message style", "Conventional commits", "250 of 270 subjects follow the pattern; the median subject is 52 characters."),
            ("typical PR size", "About 4 files and 90 changed lines per merge (median).", "Measured on 30 merge commits against their first parent. Git does not record pull requests, so this is a stand-in."),
            ("review rate", "0 of 30 merge commits carry a Reviewed-by or Approved-by line.", "Reviews held on a hosting service leave no trace in git, so this may be low."),
            ("release cadence", "No tags at this commit.", "-"))
    items += [{"kind": "workflow", "path": "", "convention": c, "observed": o, "evidence": e, "commits": []} for c, o, e in rows]
    return items


def make(tmp: Path, extend=None) -> Path:
    """Render the page. `extend(out, sha, source)`, when given, runs after the M3 extractor output is written and before the render."""
    global TOP
    home = Path(tmp) / "home"
    TOP = commit_pyrepo(Path(tmp) / "repo")
    out = home / "pyrepo"
    env = {**os.environ, "DOSSIER_HOME": str(home), "DOSSIER_CONFIG": str(Path(tmp) / "cfg.json"), "DOSSIER_CACHE": str(Path(tmp) / "cache")}
    run = lambda *a: subprocess.run(["uv", "run", str(SCRIPT), *a], capture_output=True, text=True, env=env, cwd=SKILL)
    assert run("prepare", str(TOP), "--allow-missing").returncode == 0
    facts = json.loads((out / "facts.json").read_text())
    sha = facts["repo"]["sha"]
    tree = tree_at(sha)
    source = components.source_files(set(tree), {})
    source += [f"src/generated/mod_{i:03d}.py" for i in range(GENERATED)]
    py = [p for p in source if p.endswith(".py")][:40]
    mod = lambda p: p[:-3].replace("/", ".")
    graph = [{"kind": "module", "path": p, "module": mod(p), "package": None, "is_package": False} for p in py]
    graph += [{"kind": "import", "path": a, "paths": [b], "from": mod(a), "to": mod(b), "lines": [1], "via": "grimp"} for a, b in zip(py, py[1:])]
    tests = [{"kind": "test-file", "path": p, "test_kind": "unit", "framework": "pytest", "tests": 3, "classes": 1, "skips": 0, "xfails": 0, "mocks": 0,
              "fixtures": 0, "imports": [], "paths": py[:3]} for p in [t for t in tree if re.search(r"/test_[^/]*\.py$", t)][:3]]
    dead = [{"path": py[0], "line": 3, "end_line": 3, "name": "unused_helper", "type": "function", "confidence": 60,
             "message": "unused function 'unused_helper'", "rule": "vulture.function", "snippet": "unused_helper"}]
    (out / "extract").mkdir(exist_ok=True)
    people = ["ann@example.com", "bob@example.com", "claude@example.com"]
    for name, adapter, items in (("graph", "python", graph), ("tests", "python", tests), ("dead", "python", dead), ("history", "git", history_items(source, people))):
        (out / "extract" / f"{name}.json").write_text(json.dumps(envelope(sha, adapter, items)))
    (out / "reports").mkdir(exist_ok=True)
    for rid, cards in NA_CARDS.items():
        entries = [{"card": c, "na": "The fixture page does not write this card.", "cite": ["facts:history"]} for c in cards]
        (out / "reports" / f"{rid}.json").write_text(json.dumps({"report": rid, "cards": entries}))
    flow = {"card": "interactions.flows", "blocks": [
        {"type": "diagram", "title": "Checkout from the command line", "conf": "confirmed", "cite": ["src/shopcart/cli.py:4", "src/shopcart/core.py:1", "src/shopcart/store.py:1"],
         "mermaid": "sequenceDiagram\n    participant cli as shopcart.cli\n    participant core as shopcart.core\n    participant store as shopcart.store\n"
                    "    cli->>core: checkout\n    core->>store: save", "note": ""},
        {"type": "text", "text": "1. The command line parses its arguments.\n2. The core builds the order and asks the store to save it.",
         "conf": "confirmed", "cite": ["src/shopcart/cli.py:4"]}]}
    (out / "reports" / "interactions.json").write_text(json.dumps({"report": "interactions", "cards": [flow]}))
    if extend:
        extend(out, sha, source)
    done = run("render", str(TOP), "--allow-errors")
    assert done.returncode == 0, done.stdout[-600:] + done.stderr[-600:]
    return out / "dossier-pyrepo.html"


if __name__ == "__main__":
    import tempfile
    print(make(Path(tempfile.mkdtemp())))
