#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pygments"]
# ///
"""dossier - command line behind the /dossier skill.

  dossier.py version
  dossier.py home [DIR]
  dossier.py doctor [REPO] [--all] [--json]                   list the tools a repository needs, which are installed and how to install the rest
  dossier.py clean [REPO]                                     remove the working area (clean copy, scratch home, caches) of a repository
  dossier.py prepare [REPO] [--ref REF] [--chunk-tokens N] [--full] [--allow-missing] [--no-restore] [--allow-ref] [--submodules] [--restore yes|no]
                                                              check tools, make a clean copy, install locked dependencies if allowed, measure the repo, write facts, a reading plan and an update plan
  dossier.py render  [REPO] [--partial] [--allow-errors] [--readers N]      validate the reports and write the HTML
  dossier.py candidates [REPO] --report ID [--open] [--catalog FILE] [--json]
                                                              list the tool findings a report must keep, merge or dismiss (--open: only the undecided ones)
  dossier.py correct [REPO] ...                               record a user correction
  dossier.py confirm [REPO] [IDS] ...                         list open items, or confirm / answer / dispute them
  dossier.py migrate [REPO] [--dry-run]                       one-off: convert an old-layout dossier (used for the M0 check)
"""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import buildlog  # noqa: E402
import candidates  # noqa: E402
import checks  # noqa: E402
import components  # noqa: E402
import config  # noqa: E402
import gather  # noqa: E402
import incremental  # noqa: E402
import migrate  # noqa: E402
import process  # noqa: E402
import render  # noqa: E402
import resolve  # noqa: E402
import schema  # noqa: E402
import stages  # noqa: E402
import toolcheck  # noqa: E402
import workarea  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
VERSION = (ROOT / "VERSION").read_text().strip()
CONFIG = config.path()


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
    h = config.home()
    if not h:
        die("No dossier home is set. Run /dossier home <directory> to choose where dossiers are saved.")
    return h


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
        h = config.home()
        print(f"Dossier home: {h}" if h else "No dossier home is set. Run /dossier home <directory>.")
        return
    d = Path(a.dir).expanduser().resolve()
    d.mkdir(parents=True, exist_ok=True)
    config.update(home=str(d))
    print(f"Dossier home set to {d}")


def skill_line(skill: dict) -> str:
    if skill["commit"] is None:
        return f"skill: {skill['path']} (not a git work tree)"
    if skill["unmerged"]:
        return f"skill: {skill['commit'][:7]} (UNMERGED: run git status in {skill['path']})"
    return f"skill: {skill['commit'][:7]} ({'dirty' if skill['dirty'] else 'clean'})"


def cmd_doctor(a):
    if a.all:
        report = toolcheck.preflight([], all_scopes=True)
    else:
        top = toplevel(a.repo)
        sha = subprocess.run(["git", "-C", top, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        report = toolcheck.preflight(toolcheck.languages_at(top, sha))
    skill = buildlog.skill_state(ROOT)
    if a.json:
        print(json.dumps(dict(report, skill=skill), indent=1))
    else:
        print(toolcheck.format_text(report))
        print(skill_line(skill))
    sys.exit(1 if report["missing"] or skill["unmerged"] else 0)


def cmd_clean(a):
    top = toplevel(a.repo)
    out, name, _ = out_dir(top)
    root = config.cache_root()
    area = root / out.name
    try:
        removed = workarea.clean(area, root)
    except workarea.CheckoutError as e:
        die(str(e))
    print(f"Removed the working area {area}. The dossier in {out} was not touched." if removed else f"Nothing to clean for {name}.")


def update_plan(top, out, state, facts, prev_version, full, digests=None):
    """Which reports an update must rewrite. Shifts the line numbers of citations the last commits did not touch."""
    sha = facts["repo"]["sha"]
    authored = [rid for rid, _, w in render.REPORTS if w]
    expected = incremental.expected_reports(authored, {rid for rid in authored if (out / "reports" / f"{rid}.json").exists()}, render.OPTIONAL_REPORTS)
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
                               (d or {}).get("commits_added", 0), allow_shift=not pending,
                               digest_changed=frozenset(rid for rid, dg in (digests or {}).items() if rid in (state.get("extract_digests") or {}) and state["extract_digests"][rid] != dg))
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
    opts = stages.Options(ref=a.ref, allow_missing=a.allow_missing, no_restore=a.no_restore, allow_ref=a.allow_ref,
                          submodules=a.submodules, restore=a.restore, full=a.full)
    try:
        sha = stages.resolve_ref(top, a.ref)
        area = workarea.area_for(out.name, top, root)
    except (stages.PrepareError, workarea.CheckoutError) as e:
        die(str(e))
    build = buildlog.start(out, repo=name, sha=sha, ref=a.ref, version=VERSION,
                           options={"allow_missing": a.allow_missing, "no_restore": a.no_restore, "allow_ref": a.allow_ref,
                                    "submodules": a.submodules, "full": a.full})
    try:
        pin = stages.stage_pin(build, top, a.ref, sha)
        report = stages.stage_tools(build, top, sha, opts)
        tree = stages.tree_at(top, sha)
        copy = stages.stage_copy(build, top, sha, area, state, opts, tree, pin["trust"])
        langs = [l["name"] for l in report["languages"]]
        extract = stages.stage_extract(build, top, sha, area, out, langs, pin["trust"], opts, copy["restored"], tree,
                                       copy["checkout"]["path"])
    except stages.Stop as stop:
        save_state(out, state)
        print(json.dumps(stop.payload, indent=1))
        sys.exit(stop.code)
    try:
        with buildlog.step(build, "measure") as rec:
            facts, chunks = gather.collect(top, a.ref, a.chunk_tokens, state.get("contributor_types"))
            if facts["repo"]["sha"] != sha:
                raise stages.PrepareError("The ref moved while prepare was running. Run it again.")
            if state.get("last_sha") and state["last_sha"] != sha:
                facts["delta"] = gather.delta(top, state["last_sha"], sha, state.get("snapshot"), facts)
            plan = update_plan(top, out, state, facts, prev_version, a.full, candidates.digests(candidates.load(out)))
            cached = 0
            for c in chunks["chunks"]:
                c["cached"] = (out / "notes" / f"{c['fingerprint']}.json").exists()
                cached += c["cached"]
            rec["counts"] = {"files": facts["files"]["analyzed"],
                             "languages": len([l for l in facts["languages"] if l["kind"] == "code"]),
                             "commits": facts["git"]["commits"], "contributors": facts["git"]["contributors"]["total"]}
            rec["details"] = {"reading_mode": facts["chunks"]["mode"], "chunks": len(chunks["chunks"]),
                              "chunks_with_current_notes": cached, "plan_mode": plan["mode"],
                              "stale": sorted(plan["stale"]), "fresh": plan["fresh"]}
    except stages.PrepareError as e:
        die(str(e))
    (out / "reports").mkdir(parents=True, exist_ok=True)
    (out / "notes").mkdir(parents=True, exist_ok=True)
    (out / "activity.json").write_text(json.dumps(facts.pop("file_activity", None), separators=(",", ":")))
    (out / "knowledge.json").write_text(json.dumps(facts.pop("knowledge", None), separators=(",", ":")))
    (out / "dependencies.json").write_text(json.dumps(facts.pop("dependencies", None), separators=(",", ":")))
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
        "build": str(build), "working_area": str(area), "checkout": copy["checkout"], "trust": pin["trust"],
        "preflight": {"languages": report["languages"], "missing": report["missing"]},
        "restore": copy["restore"],
        "extract": {"status": extract["status"], "reason": extract["reason"]},
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
    facts["knowledge"] = load(out / "knowledge.json")
    facts["dependencies"] = load(out / "dependencies.json")
    facts["file_lines"] = components.chunk_lines(load(out / "chunks.json", {}))
    state = load_state(out)
    reports = {}
    for rid, _, authored in render.REPORTS:
        if authored and (out / "reports" / f"{rid}.json").exists():
            reports[rid] = load(out / "reports" / f"{rid}.json")
    cites = render.Cites(facts)
    build = buildlog.load(out)          # None for a dossier made before 0.6.0: no records are written then
    build_path = out / buildlog.FILE
    errors, warnings = render.validate(reports, facts, cites, a.partial)
    extract = candidates.load(out)
    res = checks.validate(reports, extract, cites, facts)
    errors += res["errors"]
    warnings += res["warnings"]
    for i in res.get("info", []):
        print(f"info: {i}")
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}")
    unresolved = sum(1 for s_ in cites.status.values() if not s_["ok"])
    if build:
        buildlog.append(build_path, process.render_records(
            build, reports=reports, readers=None, v_errors=len(errors), cites_checked=len(cites.status),
            cites_unresolved=unresolved, gap_counts={}, check_counts=res["counts"], skill=buildlog.skill_state(ROOT))[0])
    if errors and not a.allow_errors:
        print(f"\n{len(errors)} error(s). Fix the report files and run render again.")
        sys.exit(1)

    sha = facts["repo"]["sha"]
    coverage = checks.gap_extras(build, reports, extract, cites, facts, res)
    items = render.collect_gaps(reports, coverage)
    resolve.sync(state, items)
    resolve.apply(items, state)       # decisions you made earlier apply to every build
    gaps = render.collect_gaps(reports, coverage)
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
    if build:
        for rec in process.render_records(build, reports=reports, readers=a.readers, v_errors=len(errors),
                                          cites_checked=len(cites.status), cites_unresolved=unresolved, gap_counts=counts, check_counts=res["counts"], skill=buildlog.skill_state(ROOT))[1:]:
            buildlog.append(build_path, rec)
        pending = {"step": "render", "part": "render", "by": "render", "status": "ok"}
        shown = buildlog.load(build_path)
        shown["records"].append(pending)
    else:
        shown = None
    v_errors, v_infos = process.validate_build(shown, [])
    for line in v_infos:
        print(f"info: {line}")
    for line in v_errors:
        print(f"error: {line}")
    if v_errors and not a.allow_errors:
        print(f"\n{len(v_errors)} error(s). Run prepare so build.json is complete, then render again.")
        sys.exit(1)
    page, _ = render.render_html(facts, reports, state, history, VERSION, cites, build=shown, coverage=coverage, extract=extract, checks=res)
    if build:
        buildlog.append(build_path, pending)
    name_out = f"dossier-{name}.html"
    (out / name_out).write_text(page, encoding="utf-8")
    state.update(history=history, last_sha=sha, snapshot=gather.snapshot(facts))
    state["extract_digests"] = {rid: dg for rid, dg in candidates.digests(extract).items() if rid in reports}
    state.pop("pending_update", None)
    for c in state.get("corrections", []):
        if c.get("status") != "applied" and a.apply_corrections:
            c["status"] = "applied"
    save_state(out, state)
    cites.repo.close()
    print(json.dumps({"html": str(out / name_out), "size_mb": round(len(page.encode()) / 1e6, 1), "sha": sha,
                      "reports_rendered": len(reports), "cards_filled": render.card_counts(reports)[0], "cards_pending": render.card_counts(reports)[1], "citations_checked": len(cites.status),
                      "unresolved_citations": sum(1 for s in cites.status.values() if not s["ok"]),
                      "code_viewer": cites.view_counts(),
                      "tracker": counts, "resolved_by_user": len(gaps) - sum(1 for g in gaps if render.is_open(g)), "warnings": len(warnings)}, indent=1))


def cmd_candidates(a):
    top = toplevel(a.repo)
    out, _, _ = out_dir(top)
    ids = [rid for rid, _, authored in render.REPORTS if authored]
    if a.report not in ids:
        die(f"'{a.report}' is not a report Claude writes. Use one of: {', '.join(ids)}.")
    extract = candidates.load(out)
    if not extract:
        die("No extractor output found. Run prepare first.")
    facts = load(out / "facts.json", {})
    facts["file_lines"] = components.chunk_lines(load(out / "chunks.json", {}))
    reports = {rid: load(out / "reports" / f"{rid}.json") for rid in ids if (out / "reports" / f"{rid}.json").exists()}
    catalog = load(a.catalog) if a.catalog else None
    sha = facts.get("repo", {}).get("sha")
    tree = stages.tree_at(top, sha) if sha else None
    if a.json:
        print(json.dumps(candidates.report_data(a.report, extract, reports, facts, only_open=a.open, catalog=catalog, tree=tree), indent=1))
    else:
        sys.stdout.write(candidates.text(a.report, extract, reports, facts, only_open=a.open, catalog=catalog, tree=tree))


def cmd_migrate(a):
    top = toplevel(a.repo)
    out, _, _ = out_dir(top)
    reports_dir = out / "reports"
    old = {p.stem: load(p) for p in sorted(reports_dir.glob("*.json"))}
    mapping = migrate.load_map()
    schemas = schema.load_all()
    retired = [r for r in old if r in mapping["retired"] and r not in schemas]
    stale = [r for r, sch in schemas.items() if r in old and any(c["writer"] == "claude" for c in sch["cards"]) and "cards" not in old[r]]
    if not retired and not stale:
        print("Nothing to migrate.")
        return
    result = migrate.convert(old, mapping, schemas)
    gaps_new = migrate.remap_gaps(old["gaps"], mapping["retired"]) if "gaps" in old else None
    problems = []
    for rid, rep in result["reports"].items():
        errs, _ = schema.validate(rid, rep, schemas[rid], allow_pending=True, strict_notes=False)
        problems += errs
    if problems:
        for e in problems:
            print(f"error: {e}")
        sys.exit(1)
    cards = [c for rep in result["reports"].values() for c in rep["cards"]]
    state_version = (load(out / "state.json", {}) or {}).get("skill_version") or "unknown"
    backup = out / f"reports.legacy-v{state_version}"
    summary = {"backup": str(backup), "written": list(result["reports"]),
               "cards_filled": sum(1 for c in cards if c.get("blocks")), "cards_pending": sum(1 for c in cards if c.get("pending")),
               "carried": len(result["carried"]),
               "not_carried": [{"report": r, "block": i + 1, "heading": h, "reason": why} for r, i, h, why in result["not_carried"]]}
    if a.dry_run:
        print(json.dumps(summary, indent=1))
        return
    if backup.exists():
        die(f"{backup} already exists. Move it away first; a backup is never overwritten.")
    shutil.copytree(reports_dir, backup)
    for rid, rep in result["reports"].items():
        save(reports_dir / f"{rid}.json", rep)
    if gaps_new is not None:
        save(reports_dir / "gaps.json", gaps_new)
    for rid in retired:
        (reports_dir / f"{rid}.json").unlink()
    print(json.dumps(summary, indent=1))


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
    facts = load(out / "facts.json")
    cites = render.Cites(facts) if facts else None
    items = render.collect_gaps(reports, checks.gap_extras(buildlog.load(out), reports, candidates.load(out), cites, facts))
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
    p = sub.add_parser("doctor")
    p.add_argument("repo", nargs="?")
    p.add_argument("--all", action="store_true", help="check the tools for every supported language")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_doctor)
    p = sub.add_parser("clean")
    p.add_argument("repo", nargs="?")
    p.set_defaults(fn=cmd_clean)
    p = sub.add_parser("prepare")
    p.add_argument("repo", nargs="?")
    p.add_argument("--ref", default="HEAD")
    p.add_argument("--chunk-tokens", type=int, default=400_000)
    p.add_argument("--full", action="store_true", help="rebuild every report instead of only the stale ones")
    p.add_argument("--allow-missing", action="store_true", help="carry on when tools are missing, in reduced mode")
    p.add_argument("--no-restore", action="store_true", help="do not install the repository's locked dependencies")
    p.add_argument("--allow-ref", action="store_true", help="install dependencies and run repository code even when the ref is not a tag or the default branch")
    p.add_argument("--submodules", action="store_true", help="also check out and analyse submodules")
    p.add_argument("--restore", choices=["yes", "no"], help="answer the question about installing dependencies (stored per repository)")
    p.set_defaults(fn=cmd_prepare)
    p = sub.add_parser("render")
    p.add_argument("repo", nargs="?")
    p.add_argument("--readers", type=int, help="how many parallel readers Claude used (shown on the process card)")
    p.add_argument("--partial", action="store_true", help="allow missing reports")
    p.add_argument("--allow-errors", action="store_true", help="write the HTML even if validation fails")
    p.add_argument("--apply-corrections", action="store_true", help="mark pending corrections as applied")
    p.set_defaults(fn=cmd_render)
    p = sub.add_parser("candidates")
    p.add_argument("repo", nargs="?")
    p.add_argument("--report", required=True, metavar="ID", help="the report to list findings for, such as io or components")
    p.add_argument("--open", action="store_true", help="only findings no report has decided; prints nothing when there are none")
    p.add_argument("--catalog", metavar="FILE", help="a drafted reports/components.json: show its sizes, edges and files in no component")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_candidates)
    p = sub.add_parser("migrate")
    p.add_argument("repo", nargs="?")
    p.add_argument("--dry-run", action="store_true", help="show what would change and write nothing")
    p.set_defaults(fn=cmd_migrate)
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
