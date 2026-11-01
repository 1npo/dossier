"""One-off conversion of old-layout reports (free-form blocks) into the card layout.

Exists only to turn the frozen encamp fixture into the new layout for the M0 check (docs/plans/005-m0-plan.md).
Pure functions: nothing here touches the disk except load_map.
"""
import json
import re
from pathlib import Path

import schema

MAP_PATH = Path(__file__).resolve().parent / "migrate_map.json"
MISSING_CELL = "Not yet recorded"
NOTES_HEAD = re.compile(r"^\s*notes?\s+(on|for)\b", re.I)
NOT_YET = "Not yet generated for this dossier."


def load_map(path=MAP_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _matches(rule, b):
    if not isinstance(b, dict):
        return False
    if "type" in rule and b.get("type") != rule["type"]:
        return False
    if "heading" in rule and not re.search(rule["heading"], b.get("heading") or "", re.I):
        return False
    if "mermaid" in rule and not re.search(rule["mermaid"], b.get("mermaid") or ""):
        return False
    return True


def _keep(b, keys):
    return {k: b[k] for k in keys if b.get(k) is not None}


def _convert_table(rule, b):
    old_cols = b.get("columns") or []
    new_cols = list(rule["columns"])
    rows = []
    for r in b.get("rows", []):
        cells = r.get("cells", [])
        src = [rule["columns"][c] for c in new_cols]
        new = [str(cells[old_cols.index(s)]) if s is not None and s in old_cols and old_cols.index(s) < len(cells) else MISSING_CELL for s in src]
        rows.append({"cells": new, **_keep(r, ("conf", "cite", "note"))})
    out = {"type": "table", "columns": new_cols, "rows": rows}
    if b.get("caption"):
        out["caption"] = b["caption"]
    return out


def convert(old, mapping, schemas):
    used = {}      # (old id, index) -> card id
    pending = {}   # card id -> list of (old id, index, heading, block)
    for rule in mapping["rules"]:
        blocks = old.get(rule["from"], {}).get("blocks", [])
        if not isinstance(blocks, list):
            continue
        for i, b in enumerate(blocks):
            if (rule["from"], i) in used or not _matches(rule, b):
                continue
            entries = pending.setdefault(rule["to"], [])
            heading = b.get("heading") or ""
            used[(rule["from"], i)] = rule["to"]
            if b.get("type") == "table":
                entries.append((rule["from"], i, heading, _convert_table(rule, b)))
            elif b.get("type") == "diagram":
                entries.append((rule["from"], i, heading, _keep(b, ("type", "title", "mermaid", "conf", "cite", "note"))))
                nxt = blocks[i + 1] if i + 1 < len(blocks) else None
                if rule.get("notes") == "following" and isinstance(nxt, dict) and nxt.get("type") == "text" \
                        and (rule["from"], i + 1) not in used and NOTES_HEAD.match(nxt.get("heading") or ""):
                    used[(rule["from"], i + 1)] = rule["to"]
                    entries.append((rule["from"], i + 1, nxt.get("heading") or "", _keep(nxt, ("type", "text", "conf", "cite", "note"))))
            else:
                entries.append((rule["from"], i, heading, _keep(b, ("type", "text", "items", "conf", "cite", "note"))))

    not_carried = []
    reports, filled_by_report = {}, {}
    for rid, sch in schemas.items():
        if not any(c["writer"] == "claude" for c in sch["cards"]):
            continue
        cards, n_filled = [], 0
        for card in sch["cards"]:
            if card["writer"] != "claude":
                continue
            got = pending.get(card["id"])
            entry = {"card": card["id"], "pending": True}
            if got:
                trial = {"card": card["id"], "blocks": [g[3] for g in got]}
                errs, _ = schema.validate(rid, {"cards": [trial]}, {"report": rid, "cards": [card]}, allow_pending=True)
                if errs:
                    for old_id, i, heading, _ in got:
                        used.pop((old_id, i), None)
                        not_carried.append((old_id, i, heading, "did not fit the card"))
                else:
                    entry, n_filled = trial, n_filled + 1
            cards.append(entry)
        filled_by_report[rid] = n_filled
        reports[rid] = {"cards": cards}

    for rid, rep in reports.items():
        src = old.get(mapping["primary"].get(rid, ""), {})
        if filled_by_report[rid] and src:
            rep["headline"], rep["summary"] = src.get("headline", NOT_YET), src.get("summary", "- " + NOT_YET)
        else:
            rep["headline"], rep["summary"] = NOT_YET, "- " + NOT_YET
        reports[rid] = {"headline": rep["headline"], "summary": rep["summary"], "cards": rep["cards"]}

    for oid, rep in old.items():
        if oid == "gaps":
            continue
        for i, b in enumerate(rep.get("blocks", [])):
            if (oid, i) not in used and not any(n[0] == oid and n[1] == i for n in not_carried):
                not_carried.append((oid, i, (b or {}).get("heading") or "", "no card for this content"))
    not_carried.sort(key=lambda n: (n[0], n[1]))
    carried = sorted(((o, i, next((g[2] for g in pending[c] if g[:2] == (o, i)), ""), c) for (o, i), c in used.items()))
    return {"reports": reports, "carried": carried, "not_carried": not_carried}


def remap_gaps(gaps_report, retired):
    """A copy of the gaps report with each item's 'report' set to the report that replaced the retired one."""
    out = dict(gaps_report)
    out["items"] = [{**it, "report": retired.get(it.get("report"), it.get("report"))} for it in gaps_report.get("items", [])]
    return out
