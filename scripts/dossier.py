#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pygments"]
# ///
"""dossier - command line behind the /dossier skill.

  dossier.py version
  dossier.py home [DIR]
  dossier.py prepare [REPO] [--ref REF] [--chunk-tokens N] [--full]   profile the repo, write facts, a reading plan and an update plan
  dossier.py render  [REPO] [--partial] [--allow-errors]      validate the reports and write the HTML
  dossier.py correct [REPO] ...                               record a user correction
  dossier.py confirm [REPO] [IDS] ...                         list open items, or confirm / answer / dispute them
"""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gather  # noqa: E402
import incremental  # noqa: E402
import render  # noqa: E402
import resolve  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
VERSION = (ROOT / "VERSION").read_text().strip()
CONFIG = Path(os.environ.get("DOSSIER_CONFIG") or Path.home() / ".config" / "dossier" / "config.json")


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as exc:
        die(f"{path} is not valid JSON: {exc}")


def save(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    tmp.replace(path)


def load_state(out):
    return resolve.migrate(load(out / "state.json", {}) or {})


def save_state(out, state):
    """Write state.json. When the skill version changes, keep a copy of the old file first."""
    old = out / "state.json"
    prev = state.get("skill_version")
    if old.exists() and prev and prev != VERSION:
        keep = out / f"state.backup-v{prev}.json"
        if not keep.exists():
            keep.write_text(old.read_text())
    state["skill_version"] = VERSION
    save(old, state)


# ------------------------------------------------------------------ home and paths


def get_home():
    h = os.environ.get("DOSSIER_HOME") or (load(CONFIG, {}) or {}).get("home")
    if not h:
        die("No dossier home is set. Run /dossier home <directory> to choose where dossiers are saved.")
    return Path(h).expanduser()


def toplevel(repo_arg):
    p = Path(repo_arg or ".").expanduser().resolve()
    r = subprocess.run(["git", "-C", str(p), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if r.returncode:
        die(f"'{p}' is not inside a git repository.")
    return r.stdout.strip()


def root_commit(top):
    out = subprocess.run(["git", "-C", top, "rev-list", "--max-parents=0", "HEAD"], capture_output=True, text=True).stdout.split()
    return sorted(out)[0] if out else ""


def out_dir(top):
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(top).name) or "repo"
    root = root_commit(top)
    d = get_home() / name
    st = load(d / "state.json")
    if st and st.get("repo", {}).get("root_commit") not in (None, "", root):
        d = get_home() / f"{name}-{root[:6]}"   # another repository already uses this name
    return d, name, root


# ------------------------------------------------------------------ commands


def cmd_version(_):
    print(f"dossier {VERSION}")


def cmd_home(a):
    if not a.dir:
        h = os.environ.get("DOSSIER_HOME") or (load(CONFIG, {}) or {}).get("home")
        print(f"Dossier home: {h}" if h else "No dossier home is set. Run /dossier home <directory>.")
        return
    d = Path(a.dir).expanduser().resolve()
    d.mkdir(parents=True, exist_ok=True)
    save(CONFIG, {"home": str(d)})
    print(f"Dossier home set to {d}")


def update_plan(top, out, state, facts, prev_version, full):
    """Which reports an update must rewrite. Shifts the line numbers of citations the last commits did not touch."""
    sha = facts["repo"]["sha"]
    expected = [rid for rid, _, w in render.REPORTS if w]
    paths = {rid: out / "reports" / f"{rid}.json" for rid in expected}
    reports = {rid: load(p) for rid, p in paths.items() if p.exists()}
    d, last, pending = facts["delta"], state.get("last_sha"), state.get("pending_update")
    why_full = None
    if full:
        why_full = "a full rebuild was requested"
    elif not last or not reports:
        why_full = "there is no earlier build to update"
    elif (prev_version or "").split(".")[:2] != VERSION.split(".")[:2]:
        why_full = f"the skill changed from {prev_version} to {VERSION}"
    elif d and "changed" not in d:
        why_full = d.get("note") or "the previous commit is not an ancestor of this one"
    elif d and d["files_changed"] > incremental.MAX_CHANGED:
        why_full = f"{d['files_changed']} files changed"
    if why_full:
        state.pop("pending_update", None)
        return {"mode": "full", "why": why_full, "stale": {rid: [why_full] for rid in expected}, "fresh": [], "read": [], "line_shifts": {}}

    changed = {c["path"]: c["status"][0] for c in (d or {}).get("changed", [])}
    corrections = {}
    for c in state.get("corrections", []):
        if c.get("status") != "applied":
            corrections.setdefault(c["report"], []).append(c["id"])
    resuming = bool(pending and pending["sha"] == sha)       # an earlier prepare for this commit was not rendered yet
    if resuming:
        stale = {rid: why for rid, why in pending["stale"].items()
                 if rid not in paths or not paths[rid].exists() or paths[rid].stat().st_mtime <= pending["at"]}
        for rid, ids in corrections.items():
            if rid in paths:
                stale.setdefault(rid, []).append("pending correction " + ", ".join(ids))
        shifts = {}
    else:
        def hunks_of(path):
            return incremental.parse_hunks(gather.Repo(top).git("diff", "-U0", "--no-renames", last, sha, "--", path))
        deps_changed = bool((d or {}).get("dependencies_added") or (d or {}).get("dependencies_removed"))
        res = incremental.plan(reports, expected, changed, hunks_of, deps_changed, corrections,
                               (d or {}).get("commits_added", 0), allow_shift=not pending)
        stale, shifts = res["stale"], res["shifts"]
        for rid, moves in shifts.items():
            save(paths[rid], incremental.apply_shifts(reports[rid], moves))
    if stale or shifts or last != sha:
        state["pending_update"] = {"sha": sha, "at": datetime.now().timestamp(), "stale": stale}
    fresh = [rid for rid in expected if rid not in stale]
    cited = {q for rid in stale if rid in reports for q in map(_cited_path, incremental.cites_in(reports[rid]))}
    read = sorted(p for p, st in changed.items() if st != "D" and (p in cited or any(p.startswith(c + "/") for c in cited if c)
                                                                 or posixpath.dirname(p) in {posixpath.dirname(c) for c in cited if c}))
    return {"mode": "incremental" if stale else "render_only", "why": None, "stale": stale, "fresh": fresh, "read": read,
            "line_shifts": {rid: len(m) for rid, m in shifts.items()}}


def _cited_path(raw):
    c = render.parse_cite(raw)
    return c["path"].rstrip("/") if c["kind"] == "file" else ""


def cmd_prepare(a):
    top = toplevel(a.repo)
    out, name, root = out_dir(top)
    state = load_state(out)
    prev_version = state.get("skill_version")
    state["repo"] = {"name": name, "root_commit": root}
    facts, chunks = gather.profile(top, a.ref, a.chunk_tokens, state.get("contributor_types"))
    sha = facts["repo"]["sha"]
    if state.get("last_sha") and state["last_sha"] != sha:
        facts["delta"] = gather.delta(top, state["last_sha"], sha, state.get("snapshot"), facts)
    plan = update_plan(top, out, state, facts, prev_version, a.full)
    cached = 0
    for c in chunks["chunks"]:
        c["cached"] = (out / "notes" / f"{c['fingerprint']}.json").exists()
        cached += c["cached"]
    (out / "reports").mkdir(parents=True, exist_ok=True)
    (out / "notes").mkdir(parents=True, exist_ok=True)
    (out / "activity.json").write_text(json.dumps(facts.pop("file_activity", None), separators=(",", ":")))
    save(out / "facts.json", facts)
    save(out / "chunks.json", chunks)
    save_state(out, state)
    existing = sorted(p.stem for p in (out / "reports").glob("*.json"))
    pending = [c["id"] for c in state.get("corrections", []) if c.get("status") != "applied"]
    d = facts["delta"]
    print(json.dumps({
        "out_dir": str(out), "repo": top, "name": name, "ref": a.ref, "branch": facts["repo"]["branch"], "sha": sha,
        "commits": facts["git"]["commits"], "contributors": facts["git"]["contributors"],
        "reading": {"mode": facts["chunks"]["mode"], "chunk_budget_tokens": a.chunk_tokens, "total_tokens": facts["chunks"]["total_tokens"],
                    "chunks": len(chunks["chunks"]), "chunks_with_current_notes": cached, "advice": facts["chunks"]["advice"]},
        "previous_build": ({"sha": state["last_sha"], "same_commit": state["last_sha"] == sha,
                            "commits_added": (d or {}).get("commits_added"), "files_changed": (d or {}).get("files_changed"),
                            "note": (d or {}).get("note")} if state.get("last_sha") else None),
        "update_plan": plan,
        "existing_reports": existing, "pending_corrections": pending,
        "user_decisions": [{"id": i, "decision": r["action"], "report": r.get("report"), "statement": r.get("statement"), "note": r.get("text")} for i, r in sorted(state["resolutions"].items())], "warnings": facts["repo"]["warnings"],
        "files": {"facts": str(out / "facts.json"), "chunks": str(out / "chunks.json"), "notes_dir": str(out / "notes"),
                  "reports_dir": str(out / "reports"), "state": str(out / "state.json")},
    }, indent=1))


def change_summary(facts, state):
    snap, sha = state.get("snapshot"), facts["repo"]["sha"]
    if not snap:
        return "First build of this dossier."
    if snap["sha"] == sha:
        return "Rebuilt at the same commit. The code has not changed."
    d = facts.get("delta") or {}
    if "commits_added" not in d:
        return d.get("note") or "The pinned commit changed."
    parts = [f"{d['commits_added']} new commits", f"{d['files_changed']} files changed",
             f"code lines {facts['files']['total_code_lines'] - snap['code_lines']:+,}"]
    dc = facts["git"]["contributors"]["total"] - snap["contributors"]
    if dc:
        parts.append(f"{dc:+d} contributors")
    if d.get("dependencies_added"):
        parts.append(f"{len(d['dependencies_added'])} dependencies added")
    if d.get("dependencies_removed"):
        parts.append(f"{len(d['dependencies_removed'])} dependencies removed")
    return ", ".join(parts) + "."


def cmd_render(a):
    top = toplevel(a.repo)
    out, name, _ = out_dir(top)
    facts = load(out / "facts.json")
    if not facts:
        die("No facts.json found. Run prepare first.")
    facts["file_activity"] = load(out / "activity.json")
    state = load_state(out)
    reports = {}
    for rid, _, authored in render.REPORTS:
        if authored and (out / "reports" / f"{rid}.json").exists():
            reports[rid] = load(out / "reports" / f"{rid}.json")
    cites = render.Cites(facts)
    errors, warnings = render.validate(reports, facts, cites, a.partial)
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}")
    if errors and not a.allow_errors:
        print(f"\n{len(errors)} error(s). Fix the report files and run render again.")
        sys.exit(1)

    sha = facts["repo"]["sha"]
    items = render.collect_gaps(reports)
    resolve.sync(state, items)
    resolve.apply(items, state)       # decisions you made earlier apply to every build
    gaps = render.collect_gaps(reports)
    counts = {k: sum(1 for g in gaps if g["kind"] == k and render.is_open(g)) for k in render.GAP_KINDS}
    entry = {"date": now(), "sha": sha, "short": facts["repo"]["short"], "ref": facts["repo"]["ref"], "branch": facts["repo"]["branch"],
             "skill_version": VERSION, "summary": change_summary(facts, state), "gaps": counts,
             "note": (reports.get("overview") or {}).get("update_note")}
    history = list(state.get("history", []))
    if history and history[-1]["sha"] == sha:
        entry["summary"] = history[-1]["summary"]
        entry["note"] = entry["note"] or history[-1].get("note")
        history[-1] = entry
    else:
        history.append(entry)
    page, _ = render.render_html(facts, reports, state, history, VERSION, cites)
    name_out = f"dossier-{name}.html"
    (out / name_out).write_text(page, encoding="utf-8")
    state.update(history=history, last_sha=sha, snapshot=gather.snapshot(facts))
    state.pop("pending_update", None)
    for c in state.get("corrections", []):
        if c.get("status") != "applied" and a.apply_corrections:
            c["status"] = "applied"
    save_state(out, state)
    cites.repo.close()
    print(json.dumps({"html": str(out / name_out), "size_mb": round(len(page.encode()) / 1e6, 1), "sha": sha,
                      "reports_rendered": len(reports), "citations_checked": len(cites.status),
                      "unresolved_citations": sum(1 for s in cites.status.values() if not s["ok"]),
                      "code_viewer": cites.view_counts(),
                      "tracker": counts, "resolved_by_user": len(gaps) - sum(1 for g in gaps if render.is_open(g)), "warnings": len(warnings)}, indent=1))


def cmd_correct(a):
    top = toplevel(a.repo)
    out, _, _ = out_dir(top)
    state = load_state(out) if (out / "state.json").exists() else None
    facts = load(out / "facts.json")
    if not state:
        die("Nothing to correct yet. Run prepare first.")
    sha = (facts or {}).get("repo", {}).get("sha", "")
    if a.apply:
        for c in state["corrections"]:
            if c["id"] in a.apply:
                c["status"] = "applied"
        save_state(out, state)
        print("Marked as applied: " + ", ".join(a.apply))
        return
    if a.contributor:
        if a.type not in gather.TYPES:
            die("--type must be human, agent or bot.")
        state.setdefault("contributor_types", {})[a.contributor.lower()] = a.type
        a.report, a.said, a.text = "contributors", "", f"Classify {a.contributor} as {a.type}. Takes effect on the next prepare."
    if not (a.report and a.text):
        die("Give --report and --text (and --said if you know what the dossier claimed).")
    if a.report not in render.TITLES and a.report != "other":
        die(f"--report must be one of: {', '.join(render.TITLES)}, other.")
    cid = f"C{len(state['corrections']) + 1:03d}"
    state["corrections"].append({"id": cid, "date": now(), "report": a.report, "said": a.said or "", "correction": a.text,
                                 "status": "pending", "sha": sha})
    save_state(out, state)
    print(f"Recorded {cid} (pending). Update the affected report, then run: correct --apply {cid}")


def short(t, n=150):
    t = re.sub(r"\[\[(.+?)\]\]", r"\1", " ".join(str(t).split()))
    return t if len(t) <= n else t[: n - 1] + "…"


def cmd_confirm(a):
    top = toplevel(a.repo)
    out, _, _ = out_dir(top)
    if not (out / "state.json").exists():
        die("Nothing to confirm yet. Build the dossier first.")
    state = load_state(out)
    reports = {rid: load(out / "reports" / f"{rid}.json") for rid, _, w in render.REPORTS if w and (out / "reports" / f"{rid}.json").exists()}
    if not reports:
        die("No reports found. Build the dossier first.")
    items = render.collect_gaps(reports)
    resolve.sync(state, items)
    save_state(out, state)                      # so the IDs shown here stay the same later
    res, tracked = state["resolutions"], {t["id"]: t for t in state["tracked"]}
    live = {i["id"]: i for i in items}

    if a.undo:
        for k in a.undo:
            t = resolve.find(state, k)
            if not t or t["id"] not in res:
                die(f"{k} has no recorded decision.")
            del res[t["id"]]
        save_state(out, state)
        print("Removed the decision for " + ", ".join(k.upper() for k in a.undo) + ". Run render to update the page.")
        return

    if a.ids:
        if sum(bool(x) for x in (a.answer, a.wrong)) > 1:
            die("Use only one of --answer and --wrong.")
        for k in a.ids:
            t = resolve.find(state, k)
            if not t or t["id"] not in live:
                die(f"No open item {k}. Run confirm with no IDs to list them.")
            action = "wrong" if a.wrong else "answer" if a.answer else "confirm"
            if action == "confirm" and t["kind"] == "unknown":
                die(f"{t['id']} is an unknown, so there is nothing to confirm yet. Give the answer with --answer \"...\".")
            text = (a.wrong or a.answer or a.note or "").strip()
            res[t["id"]] = {"id": t["id"], "action": action, "text": text, "date": now(), "report": t["report"], "kind": t["kind"],
                            "statement": t["statement"], "sha": (load(out / "facts.json", {}) or {}).get("repo", {}).get("sha", "")}
            if action == "wrong":
                cid = f"C{len(state['corrections']) + 1:03d}"
                state["corrections"].append({"id": cid, "date": now(), "report": t["report"], "said": t["statement"], "correction": text,
                                             "status": "pending", "sha": res[t["id"]]["sha"], "from_item": t["id"]})
                print(f"{t['id']}: recorded as disputed, and as correction {cid} (pending). Update the report, then run: correct --apply {cid}")
            else:
                print(f"{t['id']}: recorded as {'confirmed' if action == 'confirm' else 'answered'}.")
        save_state(out, state)
        print("Saved with the dossier. Run render to update the page. It applies on every later build.")
        return

    rows = [i for i in items if (a.all or i["id"] not in res or res[i["id"]]["action"] == "wrong")
            and (not a.report or i["report"] == a.report) and (not a.kind or i["kind"] == a.kind)]
    if a.json:
        print(json.dumps([{"id": i["id"], "kind": i["kind"], "report": i["report"], "statement": i["statement"], "how_to_confirm": i.get("confirm", ""),
                           "decision": (res.get(i["id"]) or {}).get("action")} for i in rows], indent=1, ensure_ascii=False))
        return
    if not rows:
        print("Nothing open." if not a.all else "No items.")
    for i in rows:
        d = res.get(i["id"])
        mark = f"  [{ {'confirm': 'confirmed', 'answer': 'answered', 'wrong': 'disputed'}[d['action']] } by you]" if d else ""
        print(f"{i['id']}  {i['kind']:<10} {render.TITLES.get(i['report'], i['report'])}{mark}\n      {short(i['statement'])}")
        if i.get("confirm"):
            print(f"      To confirm: {short(i['confirm'], 130)}")
    gone = [r for k, r in res.items() if k not in live]
    if gone:
        print(f"\n{len(gone)} saved decision(s) have no matching statement in the current reports. They are kept and apply again if the statement returns.")


def main():
    ap = argparse.ArgumentParser(prog="dossier")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("version").set_defaults(fn=cmd_version)
    p = sub.add_parser("home")
    p.add_argument("dir", nargs="?")
    p.set_defaults(fn=cmd_home)
    p = sub.add_parser("prepare")
    p.add_argument("repo", nargs="?")
    p.add_argument("--ref", default="HEAD")
    p.add_argument("--chunk-tokens", type=int, default=400_000)
    p.add_argument("--full", action="store_true", help="rebuild every report instead of only the stale ones")
    p.set_defaults(fn=cmd_prepare)
    p = sub.add_parser("render")
    p.add_argument("repo", nargs="?")
    p.add_argument("--partial", action="store_true", help="allow missing reports")
    p.add_argument("--allow-errors", action="store_true", help="write the HTML even if validation fails")
    p.add_argument("--apply-corrections", action="store_true", help="mark pending corrections as applied")
    p.set_defaults(fn=cmd_render)
    p = sub.add_parser("confirm")
    p.add_argument("repo", nargs="?", help="repository path; omit to use the current directory")
    p.add_argument("--ids", nargs="+", metavar="ID", help="item IDs to decide, such as G003 G007")
    p.add_argument("--note", help="why it is right (optional)")
    p.add_argument("--answer", help="the answer, for an unknown")
    p.add_argument("--wrong", help="what is actually true, if the item is wrong")
    p.add_argument("--undo", nargs="+", metavar="ID", help="remove a decision")
    p.add_argument("--all", action="store_true", help="when listing, include items already decided")
    p.add_argument("--report")
    p.add_argument("--kind", choices=["inference", "unknown", "assumption", "coverage"])
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_confirm)
    p = sub.add_parser("correct")
    p.add_argument("repo", nargs="?")
    p.add_argument("--report")
    p.add_argument("--said")
    p.add_argument("--text")
    p.add_argument("--apply", nargs="+")
    p.add_argument("--contributor")
    p.add_argument("--type")
    p.set_defaults(fn=cmd_correct)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
