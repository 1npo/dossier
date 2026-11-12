"""`correct` and `confirm`: record the user's corrections and their decisions on open items in the
decisions file. Never edits a report.
"""
from __future__ import annotations

import json
import re

from dossier.checks import reports as checks
from dossier.core import buildlog
from dossier.facts import gather
from dossier.findings import candidates
from dossier.findings import resolve
from dossier.render import page as render
from dossier.cli import common


def cmd_correct(a):
    top = common.toplevel(a.repo)
    out, _, _ = common.out_dir(top)
    state = common.load_state(out) if (out / "state.json").exists() else None
    facts = common.load(out / "facts.json")
    if not state:
        common.die("Nothing to correct yet. Run prepare first.")
    sha = (facts or {}).get("repo", {}).get("sha", "")
    if a.apply:
        for c in state["corrections"]:
            if c["id"] in a.apply:
                c["status"] = "applied"
        common.save_state(out, state)
        print("Marked as applied: " + ", ".join(a.apply))
        return
    if a.contributor:
        if a.type not in gather.TYPES:
            common.die("--type must be human, agent or bot.")
        state.setdefault("contributor_types", {})[a.contributor.lower()] = a.type
        a.report, a.said, a.text = "contributors", "", f"Classify {a.contributor} as {a.type}. Takes effect on the next prepare."
    if not (a.report and a.text):
        common.die("Give --report and --text (and --said if you know what the dossier claimed).")
    if a.report not in render.TITLES and a.report != "other":
        common.die(f"--report must be one of: {', '.join(render.TITLES)}, other.")
    cid = f"C{len(state['corrections']) + 1:03d}"
    state["corrections"].append({"id": cid, "date": common.now(), "report": a.report, "said": a.said or "", "correction": a.text,
                                 "status": "pending", "sha": sha})
    common.save_state(out, state)
    print(f"Recorded {cid} (pending). Update the affected report, then run: correct --apply {cid}")


def short(t, n=150):
    t = re.sub(r"\[\[(.+?)\]\]", r"\1", " ".join(str(t).split()))
    return t if len(t) <= n else t[: n - 1] + "…"


def cmd_confirm(a):
    top = common.toplevel(a.repo)
    out, _, _ = common.out_dir(top)
    if not (out / "state.json").exists():
        common.die("Nothing to confirm yet. Build the dossier first.")
    state = common.load_state(out)
    reports = {rid: common.load(out / "reports" / f"{rid}.json") for rid, _, w in render.REPORTS if w and (out / "reports" / f"{rid}.json").exists()}
    if not reports:
        common.die("No reports found. Build the dossier first.")
    facts = common.load(out / "facts.json")
    cites = render.Cites(facts) if facts else None
    items = render.collect_gaps(reports, checks.gap_extras(buildlog.load(out), reports, candidates.load(out), cites, facts))
    resolve.sync(state, items)
    common.save_state(out, state)                      # so the IDs shown here stay the same later
    res, tracked = state["resolutions"], {t["id"]: t for t in state["tracked"]}
    live = {i["id"]: i for i in items}

    if a.undo:
        for k in a.undo:
            t = resolve.find(state, k)
            if not t or t["id"] not in res:
                common.die(f"{k} has no recorded decision.")
            del res[t["id"]]
        common.save_state(out, state)
        print("Removed the decision for " + ", ".join(k.upper() for k in a.undo) + ". Run render to update the page.")
        return

    if a.ids:
        if sum(bool(x) for x in (a.answer, a.wrong)) > 1:
            common.die("Use only one of --answer and --wrong.")
        for k in a.ids:
            t = resolve.find(state, k)
            if not t or t["id"] not in live:
                common.die(f"No open item {k}. Run confirm with no IDs to list them.")
            action = "wrong" if a.wrong else "answer" if a.answer else "confirm"
            if action == "confirm" and t["kind"] == "unknown":
                common.die(f"{t['id']} is an unknown, so there is nothing to confirm yet. Give the answer with --answer \"...\".")
            text = (a.wrong or a.answer or a.note or "").strip()
            res[t["id"]] = {"id": t["id"], "action": action, "text": text, "date": common.now(), "report": t["report"], "kind": t["kind"],
                            "statement": t["statement"], "sha": (common.load(out / "facts.json", {}) or {}).get("repo", {}).get("sha", "")}
            if action == "wrong":
                cid = f"C{len(state['corrections']) + 1:03d}"
                state["corrections"].append({"id": cid, "date": common.now(), "report": t["report"], "said": t["statement"], "correction": text,
                                             "status": "pending", "sha": res[t["id"]]["sha"], "from_item": t["id"]})
                print(f"{t['id']}: recorded as disputed, and as correction {cid} (pending). Update the report, then run: correct --apply {cid}")
            else:
                print(f"{t['id']}: recorded as {'confirmed' if action == 'confirm' else 'answered'}.")
        common.save_state(out, state)
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
