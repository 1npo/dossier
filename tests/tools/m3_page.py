"""Build a page that holds every M3 card, for the V11 and V12 tests (plan 009, M3-14).

  make(tmp) -> Path to the rendered page

It copies the frozen fixture `tests/fixtures/encamp-m0`, adds extractor output made from the paths of that fixture's own repository at
its own commit, adds reports 10 and 13 whose cards Claude would write (all "not applicable"), and renders. Nothing real is read except the
file list of the repository. The numbers are made up but fixed. With 600 or so source files, the hotspot and blast-radius tables are far
taller than 40 rows.
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

FIX = SKILL / "tests" / "fixtures" / "encamp-m0"
TOP = Path(os.environ.get("DOSSIER_SUBJECT_REPO", SKILL.parent / "encamp"))  # the repository the frozen fixture was made from; only read when the fixture exists
SCRIPT = SKILL / "scripts" / "dossier.py"
NA_CARDS = {"change": ("change.unfinished", "change.decisions", "change.docs-drift"),
            "contributors": ("contributors.people", "contributors.ask", "contributors.concentration", "contributors.agents", "contributors.doubts")}


def envelope(sha, adapter, items):
    return {"schema": 1, "sha": sha, "adapters": {adapter: {"sha": sha, "version": "1", "tools": {}, "tool_status": {}, "items": items}}}


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


def number_flow_notes(reports: Path) -> None:
    """The migrated M0 notes under flow diagrams are prose or missing; the checks want numbered ones. Only this copy changes."""
    notes = {"type": "text", "text": "1. First step.\n2. Second step.", "conf": "confirmed", "cite": ["pyproject.toml"]}
    for f in reports.glob("*.json"):
        data = json.loads(f.read_text())
        for entry in data.get("cards", []):
            if entry.get("card") not in ("interactions.flows", "entry.startup") or not entry.get("blocks"):
                continue
            fixed = []
            for i, b in enumerate(entry["blocks"]):
                if b.get("type") == "diagram":
                    fixed += [b, dict(notes)]
                elif not (i and entry["blocks"][i - 1].get("type") == "diagram"):
                    fixed.append(b)
            entry["blocks"] = fixed
        f.write_text(json.dumps(data))


def make(tmp: Path, extend=None) -> Path:
    """Render the page. `extend(out, sha, source)`, when given, runs after the M3 extractor output is written and before the render."""
    home = Path(tmp) / "home"
    shutil.copytree(FIX, home / "encamp")
    for p in (home / "encamp").rglob("*"):
        p.chmod(p.stat().st_mode | 0o200)
    out = home / "encamp"
    (out / "dossier-encamp.html").unlink(missing_ok=True)
    env = {**os.environ, "DOSSIER_HOME": str(home), "DOSSIER_CONFIG": str(Path(tmp) / "cfg.json"), "DOSSIER_CACHE": str(Path(tmp) / "cache")}
    run = lambda *a: subprocess.run(["uv", "run", str(SCRIPT), *a], capture_output=True, text=True, env=env, cwd=SKILL)
    assert run("migrate", str(TOP)).returncode == 0
    facts = json.loads((out / "facts.json").read_text())
    sha = facts["repo"]["sha"]
    tree = tree_at(sha)
    source = components.source_files(set(tree), {})
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
    number_flow_notes(out / "reports")
    for rid, cards in NA_CARDS.items():
        entries = [{"card": c, "na": "The fixture page does not write this card.", "cite": ["facts:history"]} for c in cards]
        (out / "reports" / f"{rid}.json").write_text(json.dumps({"report": rid, "cards": entries}))
    if extend:
        extend(out, sha, source)
    done = run("render", str(TOP), "--allow-errors")
    assert done.returncode == 0, done.stdout[-600:] + done.stderr[-600:]
    return out / "dossier-encamp.html"


if __name__ == "__main__":
    import tempfile
    print(make(Path(tempfile.mkdtemp())))
