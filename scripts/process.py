"""The 'How this dossier was made' card, the records `render` adds to build.json, and the automatic Gaps items.

Everything here is drawn from build.json. It never imports render at module level (render imports this module).
"""
from __future__ import annotations

import html

import buildlog
import schema

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

STEP_TEXT = {
    "pin": "Pinned the repository to one commit, so everything below describes that exact state.",
    "tools": "Checked that the needed tools were installed (or listed which were missing and carried on in reduced mode).",
    "copy": "Made a clean copy of the code at that commit, and installed its locked dependencies if allowed.",
    "measure": "Measured the repository: files, languages, history, ownership, co-change.",
    "extract": "Ran the extractors to find entry points, imports, inputs and outputs, data structures and tests.",
    "read": "Read the code: how much (single read or N chunks), with how many parallel readers, and what was reused from the last build.",
    "write": "Wrote the reports: for each list a tool found, decided what to keep, merge or drop, and explained how the parts work.",
    "check": "Checked the work: citations resolve, every tool-found item is accounted for, diagrams match real dependencies, the report layout matches the standard, and the page was opened in a real browser.",
    "gaps": "Recorded the open questions in Gaps, and anything the dossier could not see.",
    "render": "Rendered the page and the machine-readable summary.",
}
PLAIN = {step: text.rstrip(".").lower() for step, text in STEP_TEXT.items()}


# ------------------------------------------------------------------ the card


def _plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def _clock(stamp):
    return (stamp or "")[11:16]


def _ok_line(step, build):
    rec = buildlog.latest(build, step)
    c, d = rec.get("counts") or {}, rec.get("details") or {}
    if step == "pin":
        t = d.get("trust") or {}
        trust = f"Trusted ref: {t.get('why')}." if t.get("trusted") else f"Not a trusted ref: {t.get('why')}."
        return f"Commit {build['sha'][:7]} ({build['ref']}). {trust}"
    if step == "tools":
        langs = ", ".join(l["name"] for l in d.get("languages", [])) or "none found"
        tools = ", ".join(f"{t['name']} {t['version']}" for t in rec.get("tools") or [])
        miss = d.get("missing") or []
        tail = f"Missing: {', '.join(miss)} (carried on with --allow-missing)." if miss else "Nothing missing."
        return f"Languages: {langs}. Tools: {tools or 'none'}. {tail}"
    if step == "copy":
        co = buildlog.latest(build, "copy", "checkout") or {}
        rs = buildlog.latest(build, "copy", "restore") or {}
        subs = (co.get("details") or {}).get("submodules") or []
        on = (co.get("details") or {}).get("submodules_on")
        sub = "none" if not subs else "on" if on else f"off ({len(subs)} not analysed)"
        eco = (rs.get("details") or {}).get("ecosystems")
        if rs.get("status") == "skipped" and not eco:
            deps = rs.get("reason") or "not recorded"
        elif eco:
            deps = ", ".join(f"{e['ecosystem']} installed ({e['seconds']:.0f} s)" if e["status"] == "ok"
                             else f"{e['ecosystem']} {e['status']}" for e in eco)
        else:
            deps = "not recorded"
        return f"Clean copy checked at {build['sha'][:7]}. Dependencies: {deps.rstrip(".")}. Submodules: {sub}."
    if step == "measure":
        return f"{c.get('files')} files, {c.get('languages')} languages, {c.get('commits')} commits, {c.get('contributors')} contributors."
    if step == "extract":
        names = ", ".join(a["name"] for a in d.get("adapters", []) if a["status"] == "ok") or "none"
        return (f"{c.get('ran', 0)} extractors ran ({names}); {c.get('reused', 0)} reused. The path filter removed "
                f"{c.get('paths_dropped', 0)} of {c.get('paths_seen', 0)} paths ({c.get('dropped_unexpected', 0)} unexpected).")
    if step == "read":
        mode = "Single read" if c.get("mode") == "single" else _plural(c.get("chunks") or 0, "chunk")
        readers = (f"{c['readers']} parallel readers, as reported by Claude" if c.get("readers")
                   else "number of parallel readers not recorded")
        return f"{mode}; notes reused for {c.get('notes_reused', 0)} of {c.get('chunks', 0)} chunks; {readers}."
    if step == "write":
        if c.get("reused"):
            return f"{_plural(c.get('written', 0), 'report')} rewritten, {c['reused']} reused."
        return f"{_plural(c.get('written', 0), 'report')} written."
    if step == "check":
        r = buildlog.latest(build, "check", "render") or {}
        rc = r.get("counts") or {}
        b = buildlog.latest(build, "check", "browser")
        browser = (f"Browser check at {_clock(b.get('started'))} UTC: {(b.get('counts') or {}).get('problems', 0)} problems."
                   if b else "Browser check: not run yet.")
        found = (f" Tool findings: {rc.get('v5_candidates', 0)} found, {rc.get('v5_open', 0)} without a decision. "
                 f"Components: {rc.get('v4', 0)} problems.") if "v5_candidates" in rc else ""
        return (f"{rc.get('citations', 0)} citations checked, {rc.get('unresolved', 0)} unresolved; "
                f"layout check: {rc.get('errors', 0)} errors.{found} {browser}")
    if step == "gaps":
        return (f"{sum(c.values())} open items: {c.get('unknown', 0)} unknown, {c.get('inference', 0)} inferred, "
                f"{c.get('assumption', 0)} assumed, {c.get('coverage', 0)} coverage.")
    if step == "render":
        return "Page written. The machine-readable summary is not produced in this version."
    return ""


def run_line(step, build):
    """One plain sentence about what the latest record of a step says, or None when there is no record."""
    if step == "check":
        rec = buildlog.latest(build, "check", "render") or buildlog.latest(build, "check")
    elif step == "copy":
        rec = buildlog.latest(build, "copy", "checkout")
        if rec and rec["status"] == "ok":
            return _ok_line("copy", build)
    else:
        rec = buildlog.latest(build, step)
    if not rec:
        return None
    if rec["status"] == "skipped":
        return f"Skipped: {rec['reason']}"
    if rec["status"] == "failed":
        return f"Failed: {rec['reason']}"
    if rec["status"] == "reused":
        return "Reused from the previous build."
    return _ok_line(step, build)


def tier_line():
    cards = [c for s in schema.load_all().values() for c in s["cards"]]
    m = sum(c["tier"] == "M" for c in cards)
    r = sum(c["tier"] == "R" for c in cards)
    return (f"Of the {len(cards)} cards in this dossier's layout, {m} are measured by tools, {len(cards) - m - r} adjudicated "
            f"(tool candidates sorted by Claude) and {r} read by Claude.")


def process_body(build) -> str:
    items = []
    for step in buildlog.STEPS:
        line = run_line(step, build)
        items.append(f"<li><p>{E(STEP_TEXT[step])}</p>"
                     f'<div class="muted">{E(line) if line is not None else "No record."}</div></li>')
    return f'<ol class="process">{"".join(items)}</ol><p class="muted">{E(tier_line())}</p>'


# ------------------------------------------------------------------ records render adds


def render_records(build, *, reports, readers, v_errors, cites_checked, cites_unresolved, gap_counts, check_counts=None) -> list[dict]:
    """The read, write, check and gaps records for this render. `check` comes first; it is part 'render'."""
    m = buildlog.latest(build, "measure") or {}
    d, c = m.get("details") or {}, m.get("counts") or {}
    out = [{"step": "check", "part": "render", "by": "render", "status": "failed" if v_errors else "ok",
            "reason": f"{v_errors} errors in the reports." if v_errors else None,
            "counts": {"citations": cites_checked, "unresolved": cites_unresolved, "errors": v_errors,
                       **{k: v for k, v in (check_counts or {}).items() if isinstance(v, int)}}}]
    if d.get("plan_mode") == "render_only":
        for step in ("read", "write"):
            out.append({"step": step, "by": "render", "status": "reused", "reason": "Nothing changed since the previous build."})
    elif not reports:
        for step in ("read", "write"):
            out.append({"step": step, "by": "render", "status": "skipped", "reason": "No reports were written in this build."})
    else:
        stale = d.get("stale") or []
        incremental = d.get("plan_mode") == "incremental"
        written = sum(1 for r in stale if r in reports) if incremental else len(reports)
        reused = sum(1 for r in d.get("fresh") or [] if r in reports) if incremental else 0
        out.append({"step": "read", "by": "render", "status": "ok",
                    "counts": {"mode": d.get("reading_mode"), "chunks": d.get("chunks", 0),
                               "notes_reused": d.get("chunks_with_current_notes", 0), "readers": readers}})
        out.append({"step": "write", "by": "render", "status": "ok", "counts": {"written": written, "reused": reused}})
    out.append({"step": "gaps", "by": "render", "status": "ok", "counts": dict(gap_counts)})
    return out


# ------------------------------------------------------------------ Gaps coverage items


def _item(statement, how):
    return {"kind": "coverage", "report": "dossier", "statement": statement, "how_to_confirm": how}


def coverage_items(build) -> list[dict]:
    """Things the dossier could not see, from what prepare recorded. Wording is fixed so item IDs stay stable."""
    if not build:
        return []
    mine = {}
    for r in build["records"]:
        if r.get("by") == "prepare":
            mine[(r["step"], r.get("part"))] = r
    items = []
    tools = mine.get(("tools", None))
    if tools:
        d = tools.get("details") or {}
        for h in d.get("host", []):
            if h["status"] == "missing":
                items.append(_item(f"The tool {h['id']} was not installed, so this build ran without it. Install it with: {h['install']}",
                                   "Install the tool and build again."))
            elif h["status"] == "old":
                items.append(_item(f"The tool {h['id']} is too old ({h['version']}; it needs {h['needs']}), so this build ran without it. "
                                   f"Install a newer one with: {h['install']}", "Install a newer version and build again."))
        for lang in d.get("languages", []):
            if lang["tier"] == "B":
                items.append(_item(f"{lang['name']} has basic support only: no import or call graph is extracted for it.",
                                   "This is a known limit of this version of dossier."))
    co, rs = mine.get(("copy", "checkout")), mine.get(("copy", "restore"))
    if co:
        dd = co.get("details") or {}
        if co["status"] == "failed":
            items.append(_item(f"Step 'copy' failed: {co['reason']}", "Fix the problem and build again."))
        if not dd.get("submodules_on"):
            for path in dd.get("submodules", []):
                items.append(_item(f"The submodule {path} was not analysed. Build with --submodules to include it.",
                                   "Build again with --submodules."))
    if rs and rs["status"] in ("skipped", "failed"):
        dd = rs.get("details") or {}
        rows = dd.get("ecosystems") or []
        if rs["status"] == "failed" or any(r["status"] != "ok" for r in rows):
            for r in rows:
                if r["status"] != "ok":
                    items.append(_item(f"Dependencies were not installed for {r['ecosystem']}: {r['reason']}",
                                       "Allow the install (or fix the problem it names) and build again."))
        elif not rows and not (rs.get("reason") or "").startswith("There is no lockfile"):
            for eco in dd.get("planned", []):
                items.append(_item(f"Dependencies were not installed for {eco}: {rs['reason']}",
                                   "Allow the install (or fix the problem it names) and build again."))
    ex = mine.get(("extract", None))
    if ex:
        if ex["status"] in ("skipped", "failed"):
            items.append(_item(f"The extractors did not run: {ex['reason']}", "Build again once the problem is fixed."))
        else:
            for a in (ex.get("details") or {}).get("adapters", []):
                if a["status"] in ("skipped", "failed"):
                    items.append(_item(f"The extractor {a['name']} did not run: {a['reason']}", "Build again once the problem is fixed."))
    for (step, part), r in mine.items():
        if r["status"] == "failed" and (step, part) not in {("tools", None), ("copy", "checkout"), ("copy", "restore"), ("extract", None)}:
            items.append(_item(f"Step '{step}' failed: {r['reason']}", "Fix the problem and build again."))
    return items


def partial_cards(build, tools=None) -> dict:
    """Card id -> why it was made without one of its tools (D7). Empty without a build record."""
    if not build:
        return {}
    import toolcheck  # late: toolcheck does not import this module, but keeps process light for the page

    tools = tools or toolcheck.load_tools()
    mine = {(r["step"], r.get("part")): r for r in build["records"] if r.get("by") == "prepare"}
    seen = ((mine.get(("tools", None)) or {}).get("details") or {})
    in_scope = {t["id"] for t in seen.get("self_installing", [])} or {t["id"] for t in tools["tools"]}
    cards_of = {t["id"]: t.get("cards") or [] for t in tools["tools"] if t["id"] in in_scope and t.get("cards")}
    absent: dict = {}

    def add(tool, why):
        if tool in cards_of:
            absent.setdefault(tool, why.rstrip("."))

    for tool in seen.get("missing", []):
        add(tool, "it is not installed")
    ex = mine.get(("extract", None))
    if ex and ex["status"] in ("skipped", "failed"):
        for tool in cards_of:
            add(tool, ex.get("reason") or "the extractors did not run")
    elif ex:
        for adapter in (ex.get("details") or {}).get("adapters", []):
            for tool, st in sorted((adapter.get("tools") or {}).items()):
                if st.get("status") in ("failed", "skipped"):
                    add(tool, st.get("reason") or "it did not run")
    reasons: dict = {}
    for tool, why in sorted(absent.items()):
        for card in cards_of[tool]:
            reasons.setdefault(card, []).append(f"Made without {tool}: {why}.")
    return {card: " ".join(r) for card, r in reasons.items()}


# ------------------------------------------------------------------ V9 and V10


def validate_build(build, pending=()) -> tuple[list[str], list[str]]:
    """V10 (errors): every fixed step has a record, and a skipped or failed one says why. V9 (info): the path filter."""
    if build is None:
        return ["V10: there is no build.json. Run prepare first."], []
    recs = list(build["records"]) + list(pending)
    errors = []
    for n, step in enumerate(buildlog.STEPS, 1):
        mine = [r for r in recs if r["step"] == step]
        if not mine:
            errors.append(f"V10: build.json has no record for step {n} '{step}' ({PLAIN[step]}).")
        for r in mine:
            if r.get("status") not in buildlog.STATUSES:
                errors.append(f"V10: step '{step}' has an unknown status '{r.get('status')}'.")
            elif r["status"] in ("skipped", "failed") and not r.get("reason"):
                errors.append(f"V10: step '{step}' was {r['status']} without a reason.")
    infos = []
    ex = next((r for r in reversed(recs) if r["step"] == "extract"), None)
    if ex is not None:
        if ex["status"] in ("skipped", "failed"):
            infos.append("V9: no extractor ran in this build, so the path filter had nothing to check.")
        else:
            c, unexpected = ex.get("counts") or {}, (ex.get("details") or {}).get("unexpected") or []
            infos.append(f"V9: the path filter removed {c.get('paths_dropped', 0)} of {c.get('paths_seen', 0)} extracted paths "
                         f"({c.get('dropped_expected', 0)} generated or installed, {c.get('dropped_outside', 0)} outside the copy, "
                         f"{c.get('dropped_unexpected', 0)} unexpected).")
            if unexpected:
                more = f", and {len(unexpected) - 20} more (see build.json)" if len(unexpected) > 20 else ""
                infos.append(f"V9: unexpected paths: {', '.join(unexpected[:20])}{more}")
    return errors, infos
