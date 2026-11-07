"""The 'How this dossier was made' card, the records `render` adds to build.json, and the automatic Gaps items.

Everything here is drawn from build.json. It never imports render at module level (render imports this module).
"""
from __future__ import annotations

import html

import buildlog
import schema
import toolcheck

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


def _extractors(build) -> str:
    """The extractors that ran (status ok) with their versions, in the order of tools.json.

    The status comes from `details.tool_status`, which is read from the extract files and so covers a reused adapter. A build
    that has none (made before 0.8.0) falls back to the adapters that ran this time.
    """
    rec = buildlog.latest(build, "extract") or {}
    status = (rec.get("details") or {}).get("tool_status")
    if status:
        ran = {n for n, t in status.items() if (t or {}).get("status") == "ok"}
        versions = {n: (t or {}).get("version") for n, t in status.items()}
    else:
        ran = {name for a in (rec.get("details") or {}).get("adapters", []) for name, t in (a.get("tools") or {}).items() if (t or {}).get("status") == "ok"}
        versions = {t["name"]: t.get("version") for t in rec.get("tools") or []}
    order = {t["id"]: i for i, t in enumerate(toolcheck.load_tools()["tools"])}
    return ", ".join(f"{n} {versions[n]}" if versions.get(n) else n for n in sorted(ran, key=lambda n: (order.get(n, len(order)), n)))


def _skill_sentence(skill) -> str:
    if not skill or not skill.get("commit"):
        return ""
    extra = (", uncommitted changes" if skill.get("dirty") else "") + (", UNMERGED" if skill.get("unmerged") else "")
    return f" Skill: {skill['commit'][:7]}{extra}."


def _ok_rows(step, build) -> list:
    """What a finished step did, as (label, value) pairs of plain text. The card shows them as a small table; `run_line` joins them into a sentence."""
    rec = buildlog.latest(build, step)
    c, d = rec.get("counts") or {}, rec.get("details") or {}
    if step == "pin":
        t = d.get("trust") or {}
        return [("Commit", f"{build['sha'][:7]} ({build['ref']})"), ("Trusted ref" if t.get("trusted") else "Not a trusted ref", t.get("why") or "")]
    if step == "tools":
        langs = ", ".join(l["name"] for l in d.get("languages", [])) or "none found"
        host = ", ".join(f"{t['name']} {t['version']}" for t in rec.get("tools") or [])
        miss = d.get("missing") or []
        out = [("Languages", langs), ("Host", host or "none"), ("Extractors", _extractors(build) or "none recorded"),
               ("Missing", f"{', '.join(miss)} (carried on with --allow-missing)" if miss else "nothing")]
        skill = d.get("skill")
        if skill and skill.get("commit"):
            out.append(("Skill", skill["commit"][:7] + (", uncommitted changes" if skill.get("dirty") else "") + (", UNMERGED" if skill.get("unmerged") else "")))
        return out
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
        return [("Clean copy", f"checked at {build['sha'][:7]}"), ("Dependencies", deps.rstrip(".")), ("Submodules", sub)]
    if step == "measure":
        return [("Files", c.get("files")), ("Languages", c.get("languages")), ("Commits", c.get("commits")), ("Contributors", c.get("contributors"))]
    if step == "extract":
        names = ", ".join(a["name"] for a in d.get("adapters", []) if a["status"] == "ok") or "none"
        return [("Extractors run", f"{c.get('ran', 0)} ({names})"), ("Reused", c.get("reused", 0)),
                ("Paths filtered out", f"{c.get('paths_dropped', 0)} of {c.get('paths_seen', 0)} ({c.get('dropped_unexpected', 0)} unexpected)")]
    if step == "read":
        mode = "Single read" if c.get("mode") == "single" else _plural(c.get("chunks") or 0, "chunk")
        readers = f"{c['readers']}, as reported by Claude" if c.get("readers") else "not recorded"
        return [("Mode", mode), ("Notes reused", f"{c.get('notes_reused', 0)} of {_plural(c.get('chunks', 0), 'chunk')}"), ("Parallel readers", readers)]
    if step == "write":
        out = [("Reports written", c.get("written", 0))]
        return out + ([("Reports reused", c["reused"])] if c.get("reused") else [])
    if step == "check":
        r = buildlog.latest(build, "check", "render") or {}
        rc = r.get("counts") or {}
        b = buildlog.latest(build, "check", "browser")
        out = [("Citations", f"{rc.get('citations', 0)} checked, {rc.get('unresolved', 0)} unresolved"), ("Layout check", _plural(rc.get("errors", 0), "error"))]
        if "v5_candidates" in rc:
            out += [("Tool findings", f"{rc.get('v5_candidates', 0)} found, {rc.get('v5_open', 0)} without a decision"),
                    ("Components", _plural(rc.get("v4", 0), "problem"))]
        if "v2" in rc:
            out.append(("Names", f"{rc['v2']} not found in the code they cite"))
        if "v3_checked" in rc:
            out.append(("Diagram arrows", f"{rc.get('v3', 0)} of {rc['v3_checked']} have no import or call behind them"))
        if "v5_people" in rc:
            out.append(("People and components", f"{rc['v5_people']} missing"))
        audit = buildlog.latest(build, "check", "audit")
        if audit:
            out.append(("Page", _plural((audit.get("counts") or {}).get("v11", 0), "problem")))
        summary = buildlog.latest(build, "check", "summary")
        if summary:
            out.append(("Summary", _plural((summary.get("counts") or {}).get("v8", 0), "problem")))
        out.append(("Browser check", f"{_plural((b.get('counts') or {}).get('problems', 0), 'problem')} ({_clock(b.get('started'))} UTC)" if b else "not run yet"))
        return out
    if step == "gaps":
        return [("Open items", sum(c.values())), ("Unknown", c.get("unknown", 0)), ("Inferred", c.get("inference", 0)),
                ("Assumed", c.get("assumption", 0)), ("Coverage", c.get("coverage", 0))]
    if step == "render":
        summary = buildlog.latest(build, "check", "summary")
        bad = (summary.get("counts") or {}).get("v8", 0) if summary else 0
        return [("Page", "written"), ("Summary file", f"not written ({_plural(bad, 'problem')})" if bad else "written")]
    return []


def _sentence(rows) -> str:
    return " ".join(f"{k}: {v}" if str(v).endswith(".") else f"{k}: {v}." for k, v in rows)


def _status_line(step, build):
    """The sentence for a step that was skipped, failed or reused, or None for one that ran."""
    rec = _record(step, build)
    if rec and rec["status"] == "skipped":
        return f"Skipped: {rec['reason']}"
    if rec and rec["status"] == "failed":
        return f"Failed: {rec['reason']}"
    if rec and rec["status"] == "reused":
        return "Reused from the previous build."
    return None


def _record(step, build):
    if step == "check":
        return buildlog.latest(build, "check", "render") or buildlog.latest(build, "check")
    if step == "copy":
        return buildlog.latest(build, "copy", "checkout")
    return buildlog.latest(build, step)


def run_line(step, build):
    """One plain sentence about what the latest record of a step says, or None when there is no record."""
    rec = _record(step, build)
    if not rec:
        return None
    return _status_line(step, build) or _sentence(_ok_rows(step, build))


def run_cell(step, build) -> str:
    """The What happened cell: a small two-column table for a step that ran, a sentence for one that did not, 'No record.' for none."""
    rec = _record(step, build)
    if not rec:
        return "No record."
    line = _status_line(step, build)
    if line is not None:
        return E(line)
    body = "".join(f'<tr><th scope="row">{E(k)}</th><td>{E(v)}</td></tr>' for k, v in _ok_rows(step, build))
    return f'<table class="happened"><tbody>{body}</tbody></table>'


def tier_line():
    cards = [c for s in schema.load_all().values() for c in s["cards"]]
    m = sum(c["tier"] == "M" for c in cards)
    r = sum(c["tier"] == "R" for c in cards)
    return (f"Of the {len(cards)} cards in this dossier's layout, {m} are measured by tools, {len(cards) - m - r} adjudicated "
            f"(tool candidates sorted by Claude) and {r} read by Claude.")


def _status_badges(step, build, badge) -> str:
    """The status badge of a step, and for `check` a second badge for the browser check."""
    rec = _record(step, build)
    if not rec:
        out = badge("no record", "", "destructive")
    else:
        out = badge(rec["status"], "", {"ok": "secondary", "failed": "destructive"}.get(rec["status"], "outline"))
    if step == "check":
        b = buildlog.latest(build, "check", "browser")
        if b is None:
            out += badge("browser: not run", "", "destructive")
        else:
            n = (b.get("counts") or {}).get("problems", 0)
            out += badge(f"browser: {_plural(n, 'problem')}", "", "secondary" if n == 0 else "destructive")
    return out


def process_body(build) -> str:
    import render  # imported late: render imports this module

    rows = []
    for n, step in enumerate(buildlog.STEPS, 1):
        rows.append([(str(n), n), E(STEP_TEXT[step]), run_cell(step, build), _status_badges(step, build, render.badge)])
    table = render.render_table(["No.", "Step", "What happened", "Status"], rows, None, "t-dossier-process", filterable=False, plain=True, sort=False)
    return f'{table}<p class="muted">{E(tier_line())}</p>'


# ------------------------------------------------------------------ records render adds


def render_records(build, *, reports, readers, v_errors, cites_checked, cites_unresolved, gap_counts, check_counts=None, skill=None) -> list[dict]:
    """The read, write, check and gaps records for this render. `check` comes first; it is part 'render'."""
    m = buildlog.latest(build, "measure") or {}
    d, c = m.get("details") or {}, m.get("counts") or {}
    out = [{"step": "check", "part": "render", "by": "render", "status": "failed" if v_errors else "ok",
            "reason": f"{v_errors} errors in the reports." if v_errors else None,
            "counts": {"citations": cites_checked, "unresolved": cites_unresolved, "errors": v_errors,
                       **{k: v for k, v in (check_counts or {}).items() if isinstance(v, int)}}}]
    if skill:
        out[0]["details"] = {"skill": skill}
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


def _item(statement, how, report="dossier"):
    return {"kind": "coverage", "report": report, "statement": statement, "how_to_confirm": how}


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
            if h.get("optional"):
                continue
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
                else:
                    for tool, st in sorted((a.get("tools") or {}).items()):
                        if st.get("status") in ("failed", "skipped"):
                            items.append(_item(f"The tool {tool} did not finish, so the cards that use it are marked partial: {st.get('reason') or 'it did not run'}",
                                               "Fix the problem and build again."))
    items += history_items(((mine.get(("measure", None)) or {}).get("details") or {}).get("history"))
    for (step, part), r in mine.items():
        if r["status"] == "failed" and (step, part) not in {("tools", None), ("copy", "checkout"), ("copy", "restore"), ("extract", None)}:
            items.append(_item(f"Step '{step}' failed: {r['reason']}", "Fix the problem and build again."))
    return items


def history_items(meta) -> list[dict]:
    """Gaps for a history that was cut short (D9). `meta` is the `meta` item of extract/history.json, or None."""
    if not meta:
        return []
    items = []
    if meta.get("shallow"):
        items.append(_item(f"This is a shallow clone, so the history covers only {meta['commits_seen']} commits. "
                           "Hotspots, co-change, ownership and workflow figures are incomplete.", "Build from a full clone.", "change"))
    if meta.get("stopped_early"):
        items.append(_item(f"Reading the history took too long, so only the newest {meta['commits_seen']} of {meta['commits_total']} commits were used.",
                           "Raise timeouts.history in the dossier config and build again.", "change"))
    if meta.get("blame_done", 0) < meta.get("blame_total", 0):
        items.append(_item(f"Only {meta['blame_done']} of {meta['blame_total']} files have line ownership, because git blame ran out of time. "
                           "The rest count commits only.", "Build again on a faster machine.", "contributors"))
    if meta.get("owner_status") == "partial":
        items.append(_item(f"Pull request approvals could not be read, so commits by agents and bots count for their authors: {meta.get('owner_reason')}",
                           "Run gh auth login, or install gh, and build again.", "contributors"))
    return items


HISTORY_CARDS = ("change.hotspots", "change.cochange", "change.blast-radius", "contributors.people", "contributors.ask",
                 "contributors.concentration", "contributors.agents", "contributors.workflow")
OWNER_CARDS = ("contributors.ask", "contributors.concentration")


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
    meta = (mine.get(("measure", None), {}).get("details") or {}).get("history") or {}
    if meta.get("status") == "partial" and meta.get("reasons"):
        for card in HISTORY_CARDS:
            reasons.setdefault(card, []).append(f"Made from incomplete history: {meta['reasons'][0]}.")
    if meta.get("owner_status") == "partial":
        for card in OWNER_CARDS:
            reasons.setdefault(card, []).append(f"Made without pull request approvals: {meta.get('owner_reason')}.")
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
