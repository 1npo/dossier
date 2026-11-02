"""V3: every arrow in a flow diagram has an import or a call behind it (D9). Warnings only; unbacked arrows are listed as inferred.

Split out of `checks.py` to keep that module short. Pure functions: they read the reports and the extractor output, never the repository.
"""
from __future__ import annotations

import re

import components
import schema

FLOW_CARDS = ("entry.startup", "interactions.flows")
SKIP_LINE = re.compile(r"^\s*(%%|flowchart\b|graph\b|subgraph\b|end\s*$|style\b|classDef\b|class\b|click\b|direction\b|linkStyle\b)")
SEQ_ARROW = re.compile(r"^\s*([\w.]+)\s*(-->>|->>|-->|->|--x|-x|--\)|-\))\s*[+\-]?\s*([\w.]+)")
PARTICIPANT = re.compile(r"^\s*(?:participant|actor)\s+([\w.]+)(?:\s+as\s+(.+?))?\s*$")
EDGE_TEXT = re.compile(r"--+\s+[^-<>=|]*?\s+--+>|-\.+\s+[^-<>=|]*?\s+\.+->|==+\s+[^-<>=|]*?\s+==+>")
EDGE_OP = re.compile(r"\s*(?:<?-->|<?-\.+->|<?==+>|---)\s*(?:\|[^|]*\|)?\s*")
NODE = re.compile(r'^(\w+)\s*(?:\[\[?"?(.*?)"?\]?\]|\(+"?(.*?)"?\)+|\{+"?(.*?)"?\}+)?$')


def _clean(label) -> str:
    return re.split(r"<br\s*/?>", str(label or ""), flags=re.I)[0].strip().strip('"`').strip()


def sequence_arrows(src: str) -> list:
    """[(from node, to node)] of a sequence diagram; a node is `(id, label)`. Dashed arrows are replies and run from the receiver."""
    labels, arrows = {}, []
    for line in src.splitlines():
        p = PARTICIPANT.match(line)
        if p:
            labels[p.group(1)] = _clean(p.group(2)) if p.group(2) else p.group(1)
            continue
        m = SEQ_ARROW.match(line)
        if m:
            a, op, b = m.groups()
            pair = (b, a) if op.startswith("--") else (a, b)
            arrows.append(pair)
    return [((a, labels.get(a, a)), (b, labels.get(b, b))) for a, b in arrows]


def flowchart_arrows(src: str) -> list:
    """[(from node, to node)] of a flowchart; a node is `(id, label)`. Chains give one arrow per link."""
    labels, arrows = {}, []
    for line in src.splitlines():
        if not line.strip() or SKIP_LINE.match(line):
            continue
        parts = [x.strip() for x in EDGE_OP.split(EDGE_TEXT.sub("-->", line)) if x.strip()]
        ids = []
        for part in parts:
            for piece in (x.strip() for x in part.split("&")):
                m = NODE.match(piece)
                if not m:
                    continue
                label = next((g for g in m.groups()[1:] if g), None)
                if label:
                    labels[m.group(1)] = _clean(label)
                ids.append((m.group(1), len(ids)))
        flat = [i for i, _ in ids]
        arrows += list(zip(flat, flat[1:]))
    return [((a, labels.get(a, a)), (b, labels.get(b, b))) for a, b in arrows]


class Resolver:
    """Maps the name of a diagram node to the modules it stands for; an empty set means the node is outside the code (a user, a service)."""

    def __init__(self, extract: dict, catalog_rows: list):
        graph = extract.get("graph", [])
        mods = [g for g in graph if g.get("kind") == "module"]
        self.by_name = {m["module"]: m for m in mods}
        self.by_path = {m["path"]: m["module"] for m in mods}
        self.by_last: dict = {}
        for m in mods:
            self.by_last.setdefault(m["module"].rsplit(".", 1)[-1], []).append(m["module"])
        self.rows = catalog_rows
        self.imports = {(g["from"], g["to"]) for g in graph if g.get("kind") == "import"}
        self.refs = {(e["path"], e["paths"][0]) for e in extract.get("symbols", []) if e.get("kind") == "ref-edge" and e.get("paths")}

    def modules(self, node) -> set:
        for name in dict.fromkeys(_clean(x) for x in node):
            if name in self.by_name:
                return {name}
            if len(self.by_last.get(name, ())) == 1:
                return {self.by_last[name][0]}
            if name in self.by_path:
                return {self.by_path[name]}
            for row in self.rows:
                if row["name"].casefold() == name.casefold():
                    return {m for p, m in self.by_path.items() if components.component_of(p, [row])[0]}
        return set()

    def backed(self, a: set, b: set) -> bool:
        if a & b:
            return True
        if any((x, y) in self.imports for x in a for y in b):
            return True
        path_of = {m: p for p, m in self.by_path.items()}
        return any((path_of.get(x), path_of.get(y)) in self.refs for x in a for y in b)


def _diagrams(entry: dict) -> list:
    return [b for b in entry.get("blocks") or [] if isinstance(b, dict) and b.get("type") == "diagram" and isinstance(b.get("mermaid"), str)]


def arrows_of(src: str) -> list:
    first = next((l.strip() for l in src.splitlines() if l.strip() and not l.strip().startswith("%%")), "")
    if first.startswith("sequenceDiagram"):
        return sequence_arrows(src)
    if first.startswith(("flowchart", "graph")):
        return flowchart_arrows(src)
    return []


def v3(reports: dict, extract: dict, catalog_rows=None) -> tuple[list, list, list, dict, dict]:
    """(errors, warnings, gaps, counts, unbacked). `unbacked` maps "card id#n" (n counts the card's diagrams from 1) to ["A → B", ...]."""
    warnings, gaps, unbacked = [], [], {}
    counts = {"v3": 0, "v3_checked": 0}
    if not any(g.get("kind") == "module" for g in (extract or {}).get("graph", [])):
        return [], warnings, gaps, counts, unbacked
    titles = {c["id"]: c["title"] for sch in schema.load_all().values() for c in sch["cards"]}
    res = Resolver(extract, catalog_rows or [])
    for rid, rep in sorted(reports.items()):
        for entry in (rep or {}).get("cards") or []:
            if not isinstance(entry, dict) or entry.get("card") not in FLOW_CARDS:
                continue
            for n, block in enumerate(_diagrams(entry), 1):
                for a, b in arrows_of(block["mermaid"]):
                    ma, mb = res.modules(a), res.modules(b)
                    if not ma or not mb:
                        continue
                    counts["v3_checked"] += 1
                    if res.backed(ma, mb):
                        continue
                    counts["v3"] += 1
                    title, na, nb = titles[entry["card"]], a[1], b[1]
                    warnings.append(f"V3: {title}, diagram {n}: the arrow {na} → {nb} has no import or call behind it.")
                    unbacked.setdefault(f"{entry['card']}#{n}", []).append(f"{na} → {nb}")
                    gaps.append({"kind": "inference", "report": rid,
                                 "statement": f"In {title}, the arrow from {na} to {nb} has no import or call behind it in the code.",
                                 "how_to_confirm": "Read the two parts and check how one reaches the other (for example through a callback or a registry)."})
    return [], warnings, gaps, counts, unbacked
