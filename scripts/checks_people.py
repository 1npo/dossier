"""V5 checks for reports 13 and 14 that look at who and what a card names, not at its layout."""
from __future__ import annotations

import re

import candidates
import schema

STATUSES = ("single owner", "departed", "shared")
RISK_SOURCES = ("extractor", "read")


def risk_source(reports: dict) -> list:
    """Every row of Risks says whether a tool found the risk (extractor) or Claude read it (read)."""
    entry = next((e for e in ((reports or {}).get("risks") or {}).get("cards") or [] if isinstance(e, dict) and e.get("card") == "risks.tracker"), None)
    if not entry or "blocks" not in entry:
        return []
    out = []
    for block in entry["blocks"]:
        columns = block.get("columns") or [] if isinstance(block, dict) else []
        if "Source" not in columns:
            continue
        at = columns.index("Source")
        for row in block.get("rows") or []:
            cells = row.get("cells") or []
            cell = str(cells[at]).strip() if at < len(cells) else ""
            if cell.lower() not in RISK_SOURCES:
                out.append(f"V5: Risks: Source must be extractor or read, found '{cell}'.")
    return out


def _entry(reports, cid):
    for e in ((reports or {}).get(cid.split(".")[0]) or {}).get("cards") or []:
        if isinstance(e, dict) and e.get("card") == cid:
            return e
    return None


def _rows(entry):
    """(columns, rows) of every table of a card entry. A not-applicable card has none."""
    return [(b.get("columns") or [], r) for b in (entry or {}).get("blocks") or [] if isinstance(b, dict) for r in b.get("rows") or [] if isinstance(r, dict)]


def _cell(columns, row, name):
    cells = row.get("cells") or []
    return str(cells[columns.index(name)]) if name in columns and columns.index(name) < len(cells) else ""


def _key(text):
    return schema._norm(re.sub(r"\[\[.*?\]\]", "", str(text)))


def _names(entry, column):
    return {_key(_cell(cols, row, column)) for cols, row in _rows(entry)}


def _known(reports, cid):
    """False when the card is missing or still pending: V6 reports that, so these checks stay quiet."""
    entry = _entry(reports, cid)
    return bool(entry) and not entry.get("pending") and ("blocks" in entry or "na" in entry)


def people(reports, extract, catalog):
    """Report 13 names every person, every agent and every component, and nobody who is not in this build (D7)."""
    items = [i for i in (extract or {}).get("history", []) if isinstance(i, dict)]
    persons = [i for i in items if i.get("kind") == "person"]
    if not persons or not all(_known(reports, c) for c in ("contributors.people", "contributors.ask", "contributors.concentration", "contributors.agents")):
        return []
    titles = candidates.card_titles()
    entries = {c: _entry(reports, c) for c in ("contributors.people", "contributors.ask", "contributors.concentration", "contributors.agents", "contributors.doubts")}
    out = []
    listed = _names(entries["contributors.people"], "Person") | _names(entries["contributors.doubts"], "Identity")
    out += [f"V5: {titles['contributors.people']} does not list {p['name']}." for p in persons if p["type"] == "human" and _key(p["name"]) not in listed]
    agents = _names(entries["contributors.agents"], "Identity")
    helpers = [i for i in items if i.get("kind") == "assistant"]
    out += [f"V5: {titles['contributors.agents']} does not list {p['name']}." for p in persons if p["type"] in ("agent", "bot") and _key(p["name"]) not in agents]
    out += [f"V5: {titles['contributors.agents']} does not list {h['name']}." for h in helpers if _key(h["name"]) not in agents]
    components_ = [r["name"] for r in catalog or []]
    for cid, column in (("contributors.ask", "Subsystem"), ("contributors.concentration", "Area")):
        have = _names(entries[cid], column)
        out += [f"V5: {titles[cid]} has no row for the component {n}." for n in components_ if _key(n) not in have]
    out += _unknown_names(entries, titles, persons, helpers, components_)
    out += _concentration(entries["contributors.concentration"], titles["contributors.concentration"], persons)
    return out


def _unknown_names(entries, titles, persons, helpers, components_):
    people_ = {_key(p["name"]) for p in persons} | {_key(a) for p in persons for a in p.get("aliases") or []}
    agents_ = {_key(p["name"]) for p in persons if p["type"] in ("agent", "bot")} | {_key(h["name"]) for h in helpers}
    comps = {_key(n) for n in components_}
    out = []
    for cid, column, known, noun in (("contributors.people", "Person", people_, "an identity"), ("contributors.ask", "Subsystem", comps, "a component"),
                                     ("contributors.concentration", "Area", comps, "a component"), ("contributors.agents", "Identity", agents_, "an identity")):
        for cols, row in _rows(entries[cid]):
            cell = _cell(cols, row, column)
            if cell.strip() and _key(cell) not in known and (noun != "a component" or comps):
                out.append(f"V5: {titles[cid]} names {cell.strip()}, which is not {noun} in this build.")
    for cols, row in _rows(entries["contributors.concentration"]):
        owner = _cell(cols, row, "Owner")
        if owner.strip() and _key(owner) not in people_ | agents_ | {"unknown"}:
            out.append(f"V5: {titles['contributors.concentration']} names {owner.strip()}, which is not an identity in this build.")
    return out


def _concentration(entry, title, persons):
    humans = [p for p in persons if p["type"] == "human"]
    sole = humans[0]["name"] if len(humans) == 1 else None
    out = []
    for cols, row in _rows(entry):
        area, owner, status = _cell(cols, row, "Area").strip(), _cell(cols, row, "Owner"), _cell(cols, row, "Status")
        if sole and _key(owner) not in (_key(sole), "unknown"):
            out.append(f"V5: {title}, {area}: {sole} is the only person on this project, so they are the owner.")
        if _key(owner) == "unknown" and row.get("conf") != "unknown":
            out.append(f"V5: {title}, {area}: an Owner of unknown needs conf unknown.")
        if _key(status) not in STATUSES:
            out.append(f"V5: {title}, {area}: Status must be single owner, departed or shared.")
    return out
