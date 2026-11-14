"""`render`: validate the reports and write the HTML page, the summary and the build log. Runs the
browser check line from `check` for the build record.
"""
from __future__ import annotations

import json
import sys

from dossier.checks import page_audit
from dossier.checks import reports as checks
from dossier.core import buildlog
from dossier.facts import gather
from dossier.findings import candidates
from dossier.findings import components
from dossier.findings import resolve
from dossier.render import page as render
from dossier.render import portfolio
from dossier.render import process
from dossier.render import summary
from dossier.render.measured import upgrade as measured_upgrade
from dossier.cli import common
from dossier.cli.commands import check
import argparse
from typing import Any

__all__ = ["cmd_render"]


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


def _filtered_out(build) -> dict:
    """What the extract path filter removed, for the summary line."""
    c = (buildlog.latest(build, "extract") or {}).get("counts") or {} if build else {}
    return {k: c.get(k, 0) for k in ("paths_seen", "paths_dropped", "dropped_expected", "dropped_outside", "dropped_unexpected")}


def cmd_render(a: argparse.Namespace) -> Any:
    top = common.toplevel(a.repo)
    out, name, _ = common.out_dir(top)
    facts = common.load(out / "facts.json")
    if not facts:
        common.die("No facts.json found. Run prepare first.")
    facts["file_activity"] = common.load(out / "activity.json")
    facts["knowledge"] = common.load(out / "knowledge.json")
    facts["dependencies"] = common.load(out / "dependencies.json")
    if a.refresh_refdata:
        fresh = measured_upgrade.fetch_refdata()
        if fresh:
            common.save(out / "refdata.json", fresh)
        else:
            print("warning: the .NET release data could not be fetched; keeping the pinned data")
    facts["refdata"] = common.load(out / "refdata.json", {}) or {}
    facts["file_lines"] = components.chunk_lines(common.load(out / "chunks.json", {}))
    state = common.load_state(out)
    reports = {}
    for rid, _, authored in render.REPORTS:
        if authored and (out / "reports" / f"{rid}.json").exists():
            reports[rid] = common.load(out / "reports" / f"{rid}.json")
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
            cites_unresolved=unresolved, gap_counts={}, check_counts=res["counts"], skill=buildlog.skill_state(common.ROOT))[0])
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
    entry = {"date": common.now(), "sha": sha, "short": facts["repo"]["short"], "ref": facts["repo"]["ref"], "branch": facts["repo"]["branch"],
             "skill_version": common.VERSION, "summary": change_summary(facts, state), "gaps": counts,
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
                                          cites_checked=len(cites.status), cites_unresolved=unresolved, gap_counts=counts, check_counts=res["counts"], skill=buildlog.skill_state(common.ROOT))[1:]:
            buildlog.append(build_path, rec)
        pending = {"step": "render", "part": "render", "by": "render", "status": "ok"}
        shown: Any = buildlog.load(build_path)
        shown["records"].append(pending)
    else:
        shown = None
    v_errors, v_infos = process.validate_build(shown, [])
    for line in v_infos:
        print(f"{'warning' if line.startswith('V9') else 'info'}: {line}")
    for line in v_errors:
        print(f"error: {line}")
    if v_errors and not a.allow_errors:
        print(f"\n{len(v_errors)} error(s). Run prepare so build.json is complete, then render again.")
        sys.exit(1)
    def draw(records):
        return render.render_html(facts, reports, state, history, common.VERSION, cites, build=records, coverage=coverage, extract=extract, checks=res)[0]

    page = draw(shown)
    v11 = page_audit.audit(page, reports, extract, facts, build=shown,
                           measured=render.measured_ctx({"cites": cites, "extract": extract}, reports, facts))
    for line in v11:
        print(f"error: {line}")
    if build:
        audit = {"step": "check", "part": "audit", "by": "render", "status": "failed" if v11 else "ok",
                 "reason": f"{len(v11)} problems in the page." if v11 else None, "counts": {"v11": len(v11)}}
        buildlog.append(build_path, audit)
        shown["records"].append(audit)
        page = draw(shown)  # the process card now says how many problems the page audit found
    if v11 and not a.allow_errors:
        print(f"\n{len(v11)} error(s) in the drawn page. The page was not written. Fix the cause and render again.")
        sys.exit(1)
    summary_doc = summary.build(facts, reports, extract, build, counts, common.VERSION, facts.get("dependencies"), cites.tree()[0],
                                tools=candidates.tool_list(out))
    v8 = summary.validate(summary_doc)
    for line in v8:
        print(f"error: {line}")
    if build:
        record = {"step": "check", "part": "summary", "by": "render", "status": "failed" if v8 else "ok",
                  "reason": f"{len(v8)} problems in summary.json." if v8 else None, "counts": {"v8": len(v8)}}
        buildlog.append(build_path, record)
        shown["records"].append(record)
        page = draw(shown)  # the process card now says what summary.json came to
    if v8 and not a.allow_errors:
        print(f"\n{len(v8)} error(s) in summary.json. The page was not written. Fix the reports and render again.")
        sys.exit(1)
    if build:
        buildlog.append(build_path, pending)
    name_out = f"dossier-{name}.html"
    (out / name_out).write_text(page, encoding="utf-8")
    summary.remove(out) if v8 else summary.write(out, summary_doc)
    portfolio.write(common.get_home(), common.VERSION)    # the home page that lists every dossier
    state.update(history=history, last_sha=sha, snapshot=gather.snapshot(facts))
    state["extract_digests"] = {rid: dg for rid, dg in candidates.digests(extract).items() if rid in reports}
    state.pop("pending_update", None)
    for c in state.get("corrections", []):
        if c.get("status") != "applied" and a.apply_corrections:
            c["status"] = "applied"
    common.save_state(out, state)
    cites.repo.close()
    print(json.dumps({"html": str(out / name_out), "size_mb": round(len(page.encode()) / 1e6, 1), "sha": sha,
                      "reports_rendered": len(reports), "cards_filled": render.card_counts(reports)[0], "cards_pending": render.card_counts(reports)[1], "citations_checked": len(cites.status),
                      "unresolved_citations": sum(1 for s in cites.status.values() if not s["ok"]),
                      "code_viewer": cites.view_counts(),
                      "tracker": counts, "resolved_by_user": len(gaps) - sum(1 for g in gaps if render.is_open(g)), "warnings": len(warnings),
                      "tools_not_run": buildlog.tools_not_run(buildlog.load(build_path) if build else None),
                      "filtered_out": _filtered_out(buildlog.load(build_path) if build else None),
                      "browser_check": check.browser_check_line(buildlog.load(build_path) if build else None)}, indent=1))
