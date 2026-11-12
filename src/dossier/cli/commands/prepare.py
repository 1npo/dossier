from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import functools
import json
import posixpath
import sys

from dossier.core import buildlog
from dossier.core import config
from dossier.facts import gather
from dossier.findings import candidates
from dossier.history import scan as historyscan
from dossier.pipeline import incremental
from dossier.pipeline import stages
from dossier.pipeline import workarea
from dossier.render import page as render
from dossier.render.measured import upgrade as measured_upgrade
from dossier.tooling import sandbox
from dossier.cli import common


def update_plan(top, out, state, facts, prev_version, full, digests=None):
    """Which reports an update must rewrite. Shifts the line numbers of citations the last commits did not touch."""
    sha = facts["repo"]["sha"]
    authored = [rid for rid, _, w in render.REPORTS if w]
    expected = incremental.expected_reports(authored, {rid for rid in authored if (out / "reports" / f"{rid}.json").exists()}, render.OPTIONAL_REPORTS)
    paths = {rid: out / "reports" / f"{rid}.json" for rid in expected}
    reports = {rid: common.load(p) for rid, p in paths.items() if p.exists()}
    d, last, pending = facts["delta"], state.get("last_sha"), state.get("pending_update")
    why_full = None
    if full:
        why_full = "a full rebuild was requested"
    elif not last or not reports:
        why_full = "there is no earlier build to update"
    elif (prev_version or "").split(".")[:2] != common.VERSION.split(".")[:2]:
        why_full = f"the skill changed from {prev_version} to {common.VERSION}"
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
            common.save(paths[rid], incremental.apply_shifts(reports[rid], moves))
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
    top = common.toplevel(a.repo)
    out, name, root = common.out_dir(top)
    state = common.load_state(out)
    prev_version = state.get("skill_version")
    state["repo"] = {"name": name, "root_commit": root}
    opts = stages.Options(ref=a.ref, allow_missing=a.allow_missing, no_restore=a.no_restore, allow_ref=a.allow_ref,
                          submodules=a.submodules, restore=a.restore, full=a.full, verify=a.verify)
    try:
        sha = stages.resolve_ref(top, a.ref)
        area = workarea.area_for(out.name, top, root)
    except (stages.PrepareError, workarea.CheckoutError) as e:
        common.die(str(e))
    build = buildlog.start(out, repo=name, sha=sha, ref=a.ref, version=common.VERSION,
                           options={"allow_missing": a.allow_missing, "no_restore": a.no_restore, "allow_ref": a.allow_ref,
                                    "submodules": a.submodules, "full": a.full, "verify": a.verify})
    try:
        pin = stages.stage_pin(build, top, a.ref, sha, area)
        report = stages.stage_tools(build, top, sha, opts)
        tree = stages.tree_at(top, sha)
        copy = stages.stage_copy(build, top, sha, area, state, opts, tree, pin["trust"])
        langs = [l["name"] for l in report["languages"]]
        extract = stages.stage_extract(build, top, sha, area, out, langs, pin["trust"], opts, copy["restored"], tree,
                                       copy["checkout"]["path"])
    except stages.Stop as stop:
        common.save_state(out, state)
        print(json.dumps(stop.payload, indent=1))
        sys.exit(stop.code)
    try:
        with buildlog.step(build, "measure") as rec:
            facts, chunks = gather.collect(top, a.ref, a.chunk_tokens, state.get("contributor_types"))
            if facts["repo"]["sha"] != sha:
                raise stages.PrepareError("The ref moved while prepare was running. Run it again.")
            if state.get("last_sha") and state["last_sha"] != sha:
                facts["delta"] = gather.delta(top, state["last_sha"], sha, state.get("snapshot"), facts)
            handed = facts.pop("history_input")
            owners_cache = common.load(out / "github-owners.json", {}) or {}
            past = historyscan.collect(top, sha, functools.partial(sandbox.run, area=area, cwd=Path(top)), handed,
                                       config.timeouts()["history"], owners_cache, config.timeouts()["github"])
            historyscan.write(out, past)
            if owners_cache:
                common.save(out / "github-owners.json", owners_cache)
            meta = historyscan.meta_of(past)
            facts["history"] = {k: meta[k] for k in ("status", "reasons", "commits_seen", "commits_total", "shallow", "as_of")}
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
                              "stale": sorted(plan["stale"]), "fresh": plan["fresh"], "history": meta}
    except stages.PrepareError as e:
        common.die(str(e))
    (out / "reports").mkdir(parents=True, exist_ok=True)
    (out / "notes").mkdir(parents=True, exist_ok=True)
    (out / "activity.json").write_text(json.dumps(facts.pop("file_activity", None), separators=(",", ":")))
    (out / "knowledge.json").write_text(json.dumps(facts.pop("knowledge", None), separators=(",", ":")))
    (out / "dependencies.json").write_text(json.dumps(facts.pop("dependencies", None), separators=(",", ":")))
    common.save(out / "facts.json", facts)
    common.save(out / "chunks.json", chunks)
    common.save(out / "refdata.json", measured_upgrade.fetch_refdata())
    common.save_state(out, state)
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
