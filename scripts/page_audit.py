"""V11: the page draws every row, column and entry of its sources (plan 008, D10). Standard library only.

`audit` reads the HTML that `render` produced and compares it with the report files and the extractor output that fed it:
a table has its columns and one row per source row, an entries card one entry per source entry with every field, a flow
diagram its numbered notes, a drawn card the number of items its source has. It returns one error line per difference.
It never imports `render` at module level (render calls it).
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser

import buildlog
import components
import measured_blast
import measured_change
import measured_er
import measured_upgrade
import schema

VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())
SKIP_TEXT = frozenset(("script", "style"))
DRAWN_TABLES = {"data.relationships": "t-data-relationships-fields", "interactions.graph": "t-interactions-graph-edges"}


class Node:
    __slots__ = ("tag", "attrs", "kids", "chunks", "parent")

    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.kids, self.chunks, self.parent = tag, dict(attrs), [], [], parent

    def has(self, cls: str) -> bool:
        return cls in (self.attrs.get("class") or "").split()

    def walk(self):
        for k in self.kids:
            yield k
            yield from k.walk()

    def find(self, tag=None, cls=None, id=None) -> list:
        return [n for n in self.walk() if (tag is None or n.tag == tag) and (cls is None or n.has(cls)) and (id is None or n.attrs.get("id") == id)]

    def text(self) -> str:
        return " ".join((" ".join(self.chunks) + " " + " ".join(k.text() for k in self.kids)).split())


class Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {}, None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, [(k, v or "") for k, v in attrs], self.cur)
        self.cur.kids.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.kids.append(Node(tag, [(k, v or "") for k, v in attrs], self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        if self.cur.tag not in SKIP_TEXT and data.strip():
            self.cur.chunks.append(data)


def parse(page: str) -> Node:
    b = Builder()
    b.feed(page)
    b.close()
    return b.root


def _rows(table: Node) -> list:
    body = next((k for k in table.kids if k.tag == "tbody"), None)
    return [r for r in (body.kids if body else []) if r.tag == "tr"]


def _head(table: Node) -> list:
    head = next((k for k in table.kids if k.tag == "thead"), None)
    rows = [r for r in (head.kids if head else []) if r.tag == "tr"]
    return [th.text() for th in rows[-1].kids if th.tag == "th"] if rows else []


def _plain_tables(card: Node) -> list:
    return [t for t in card.find("table") if not t.has("kv")]


def _check_table(cid: str, n: int, table: Node, columns: list, rows: int, authored: bool) -> list:
    import render  # late: render calls this module
    import render  # late: render calls this module
    errs, want = [], list(columns) + (list(render.auto_columns(columns)) if authored else [])
    have = _head(table)
    for col in want:
        if col not in have:
            errs.append(f"V11: {cid}: table {n} is missing the column '{col}'.")
    if not errs and have[:len(want)] != want:
        errs.append(f"V11: {cid}: table {n} has the columns {have} where {want} are expected.")
    if len(_rows(table)) != rows:
        errs.append(f"V11: {cid}: table {n} has {len(_rows(table))} rows, expected {rows}.")
    return errs


def _note_count(block) -> int:
    """How many numbered notes a block holds (0 when it is not valid notes: V6 reports that, not V11)."""
    if not schema._numbered_notes(block):
        return 0
    return len([i for i in block["items"] if str(i).strip()]) if block.get("type") == "list" else len([ln for ln in str(block["text"]).splitlines() if ln.strip()])


def _check_flows(cid: str, card: Node, blocks: list) -> list:
    """One flow diagram per diagram block, and under each one a list with as many items as its numbered notes have lines."""
    diagrams = [(b, blocks[n + 1] if n + 1 < len(blocks) else None) for n, b in enumerate(blocks) if isinstance(b, dict) and b.get("type") == "diagram"]
    flows = card.find(cls="flow")
    if len(flows) != len(diagrams):
        return [f"V11: {cid}: {len(flows)} flow diagrams drawn, expected {len(diagrams)}."]
    errs = []
    for n, (flow, (_, notes)) in enumerate(zip(flows, diagrams), 1):
        want = _note_count(notes)
        drawn = flow.find(cls="diagram-notes")
        lists = [x for x in drawn[0].kids if x.tag in ("ol", "ul")] if drawn else []
        if want and (not lists or len(lists[0].find("li")) != want):
            errs.append(f"V11: {cid}: diagram {n} has {len(lists[0].find('li')) if lists else 0} numbered notes drawn, expected {want}.")
    return errs


def _check_entries(cid: str, card: Node, entries: list, labels: list) -> list:
    drawn = card.find("details", cls="entry")
    if len(drawn) != len(entries):
        return [f"V11: {cid}: {len(drawn)} entries drawn, expected {len(entries)}."]
    errs = []
    for n, d in enumerate(drawn, 1):
        kv = d.find("table", cls="kv")
        got = [th.text() for th in kv[0].find("th")] if kv else None
        if got is None:
            errs.append(f"V11: {cid}: entry {n} has no key/value table.")
        elif got != labels:
            errs.append(f"V11: {cid}: entry {n} lists the fields {got} where {labels} are expected.")
    return errs


def _check_entry(card: Node, cid: str, entry: dict, sch_card: dict) -> list:
    if "na" in entry:
        text = card.text()
        return [] if "Not applicable" in text and card.find(cls="cite") else [f"V11: {cid}: the 'not applicable' reason or its citation is not drawn."]
    if "blocks" in entry:
        errs, tables = [], _plain_tables(card)
        wanted = [b for b in entry["blocks"] if isinstance(b, dict) and b.get("type") == "table"]
        for n, b in enumerate(wanted, 1):
            errs += [f"V11: {cid}: table {n} is not drawn: the card has no table."] if n > len(tables) else _check_table(
                cid, n, tables[n - 1], b.get("columns") or [], len(b.get("rows") or []), True)
        if sch_card["shape"] == "flows":
            errs += _check_flows(cid, card, entry["blocks"])
        return errs
    if "entries" in entry:
        return _check_entries(cid, card, entry["entries"], [f["label"] for f in sch_card.get("fields") or []])
    return []


def _drawn_counts(extract, build) -> dict:
    """card id -> (table id, rows the source has) for the cards code draws."""
    out = {"dossier.questions": ("t-questions", len(schema.load_questions())),
           "dossier.cards": ("t-cards", sum(len(sch["cards"]) for sch in schema.load_all().values()))}
    if build is not None:  # a dossier without build.json has a placeholder in place of the process card
        out["dossier.process"] = ("t-dossier-process", len(buildlog.STEPS))
    extract = extract or {}
    if "models" in extract:
        out["data.relationships"] = (DRAWN_TABLES["data.relationships"], sum(len(e.get("fields") or []) for e in measured_er.entities(extract)))
    if "graph" in extract:
        out["interactions.graph"] = (DRAWN_TABLES["interactions.graph"], sum(1 for g in extract["graph"] if g.get("kind") == "import" and g.get("paths")))
    return out


HOTSPOT_FILES = ["File", "Component", "Commits (12 months)", "Commits (all)", "Lines", "Complexity", "Last changed", "Source"]
HOTSPOT_COMPONENTS = ["Component", "Files", "File changes (12 months)", "Lines", "Complexity"]
BLAST_COLUMNS = ["File", "Component", "Direct dependents", "All dependents", "Importing tests", "Co-changing files"]


def _measured_counts(m) -> dict:
    """card id -> [(table id, rows the source has, the columns it must start with)] for the cards code draws from the history (M3)."""
    extract = m.get("extract") or {}
    out = {}
    if not measured_change.has_history(m):
        return out
    files = components.source_files(m.get("tree"), extract)
    if files:
        out["change.hotspots"] = [("t-change-hotspots-files", len(files), HOTSPOT_FILES),
                                  ("t-change-hotspots-components", len(m.get("catalog") or []), HOTSPOT_COMPONENTS)]
    out["change.cochange"] = [("t-change-cochange", len(measured_change.pair_rows(m)), ["A", "B", "Co-commits", "Share", "Linked in code?", "Source"])]
    if "dead" in extract or "graph" in extract:
        out["change.dead-code"] = [("t-change-dead-code", len(measured_change.dead_rows(extract, (m.get("facts") or {}).get("dependencies"))),
                                    ["Item", "Kind", "Evidence", "Source"])]
    out["change.in-flight"] = [("t-change-in-flight", len(measured_change.history_items(m, "branch")), ["Branch", "Last commit", "Ahead/behind", "Author", "Source"])]
    blast = measured_blast.data(m)
    if blast:
        out["change.blast-radius"] = [("t-change-blast-radius", len(blast["files"]), BLAST_COLUMNS)]
    work = len(measured_change.history_items(m, "workflow"))
    if work:
        out["contributors.workflow"] = [("t-contributors-workflow", work, ["Convention", "Observed", "Evidence", "Source"])]
    people = [i for i in measured_change.history_items(m, "person")]
    if people:
        out["overview.contributors"] = [("t-people-owner", sum(1 for p in people if p["owned_commits"] or p["owned_lines"]),
                                         ["Name", "Type", "Commits owned", "Commits authored", "Lines owned"])]
    out["change.upgrade-burden"] = [("t-change-upgrade-burden", len(measured_upgrade.rows(m)), ["Runtime or package", "Pinned", "Latest or supported", "Gap", "Source"])]
    return out


def _check_measured(cards: dict, m, page: str) -> list:
    errs = []
    for cid, tables in _measured_counts(m).items():
        if cid not in cards:
            continue
        card = cards[cid][0]
        if "Not yet generated" in card.text():
            continue    # reported once, by the rule on change and contributors cards
        for tid, rows, cols in tables:
            found = card.find("table", id=tid)
            if rows == 0:
                if found:
                    errs.append(f"V11: {cid}: the table {tid} is drawn although the source has nothing to list.")
                if not card.find(cls="none-found"):
                    errs.append(f"V11: {cid}: the source has nothing to list for {tid}, and the card does not say so.")
                continue
            if not found:
                errs.append(f"V11: {cid}: the table {tid} is not drawn.")
                continue
            errs += _check_table(cid, tid, found[0], cols, rows, False)
    if "change.blast-radius" in cards and any(t[0] == "t-change-blast-radius" for t in _measured_counts(m).get("change.blast-radius", [])):
        want = _measured_counts(m)["change.blast-radius"][0][1]
        raw = re.search(r'<script type="application/json" id="blast-data">(.*?)</script>', page, re.S)
        try:
            got = len(json.loads(raw.group(1).replace("<\\/", "</"))["files"]) if raw else None
        except (ValueError, KeyError, TypeError):
            got = None
        if got != want:
            errs.append(f"V11: change.blast-radius: blast-data holds {got} files, expected {want}.")
    return errs


def _check_unfinished(cards: dict) -> list:
    import render  # late: render calls this module

    return [f"V11: {cid}: the card still says 'Not yet generated'." for cid, v in sorted(cards.items())
            if cid.startswith(("change.", "contributors.")) and cid not in render.CUT_CARDS and "Not yet generated" in v[0].text()]


def audit(page: str, reports: dict, extract=None, facts=None, whole_page=True, build=None, measured=None) -> list:
    """V11 errors for the page `page` (or any HTML holding the cards): [] when it draws everything its sources hold."""
    root = parse(page)
    cards: dict = {}
    for n in root.walk():
        if "data-card" in n.attrs:
            cards.setdefault(n.attrs["data-card"], []).append(n)
    errs = []
    sch_cards = {c["id"]: c for sch in schema.load_all().values() for c in sch["cards"]}
    if whole_page:
        for cid in sch_cards:
            if cid not in cards:
                errs.append(f"V11: the card {cid} is not on the page.")
    errs += [f"V11: the card {cid} is on the page {len(v)} times." for cid, v in cards.items() if len(v) > 1]
    for rid, rep in sorted((reports or {}).items()):
        for entry in (rep or {}).get("cards") or []:
            cid = entry.get("card") if isinstance(entry, dict) else None
            if cid not in cards or cid not in sch_cards or sch_cards[cid]["writer"] != "claude" or "pending" in entry:
                continue
            card = cards[cid][0]
            if "Not yet generated" in card.text():
                errs.append(f"V11: {cid}: the card still says 'Not yet generated' although the report holds it.")
                continue
            errs += _check_entry(card, cid, entry, sch_cards[cid])
    for cid, (tid, rows) in _drawn_counts(extract, build).items():
        if cid in cards:
            table = cards[cid][0].find("table", id=tid)
            if not table:
                errs.append(f"V11: {cid}: the table {tid} is not drawn.")
            elif len(_rows(table[0])) != rows:
                errs.append(f"V11: {cid}: the table has {len(_rows(table[0]))} rows, expected {rows}.")
    errs += _check_unfinished(cards)
    if measured is not None:
        errs += _check_measured(cards, measured, page)
    return errs
