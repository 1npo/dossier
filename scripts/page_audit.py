"""V11: the page draws every row, column and entry of its sources (plan 008, D10). Standard library only.

`audit` reads the HTML that `render` produced and compares it with the report files and the extractor output that fed it:
a table has its columns and one row per source row, an entries card one entry per source entry with every field, a flow
diagram its numbered notes, a drawn card the number of items its source has. It returns one error line per difference.
It never imports `render` at module level (render calls it).
"""
from __future__ import annotations

import json
from html.parser import HTMLParser

import buildlog
import measured_er
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
    errs, want = [], list(columns) + (["Basis", "Source"] if authored else [])
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


def audit(page: str, reports: dict, extract=None, facts=None, whole_page=True, build=None) -> list:
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
    return errs
