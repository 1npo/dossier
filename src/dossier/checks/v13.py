"""V13: the hand-written cards that no tool feeds must cover every component.

Source of truth, Lifecycle and sensitive fields, Business rules and invariants, Key flows and Extension points are only
checked for shape by V6. Nothing else notices when a whole component is never mentioned. For each of those cards, every
component of the catalog must be touched by at least one row, list item or diagram, or be listed in the card's
`not_applicable` with a reason. A row touches a component when one of its citations is a file inside the component's
`Paths`, or when its text names the component. A component of more than `ERROR_LINES` source lines is an error when
missed; a smaller one is a warning. In Key flows, every component that holds an entry point must also appear.
"""
from __future__ import annotations

import re

from dossier.findings import candidates, components
from dossier.render import markup

__all__ = ["CARDS", "ERROR_LINES", "v13"]

CARDS = ("data.truth", "data.lifecycle", "behavior.rules", "interactions.flows", "components.extension-points")
ERROR_LINES = 300


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for k, v in node.items():
            if k not in ("conf", "user", "was", "gid"):
                yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)


def _cited_paths(node):
    """Every file or folder a node cites, in its `cite` lists and in inline [[...]] marks."""
    raws = []

    def walk(n):
        if isinstance(n, dict):
            raws.extend(x for x in n.get("cite") or [] if isinstance(x, str))
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(node)
    raws += markup.inline_cites(*_strings(node))
    for raw in raws:
        c = markup.parse_cite(raw)
        if c["kind"] == "file":
            yield c["path"].rstrip("/")


def touched(entry: dict, rows: list) -> set:
    """The names of the catalog components that a card entry cites or names."""
    names = set()
    text = "\n".join(_strings({k: v for k, v in entry.items() if k not in ("not_applicable", "cite")}))
    for path in _cited_paths(entry):
        for probe in (path, path + "/_"):
            owner, tied = components.component_of(probe, rows)
            if owner:
                names |= {owner, *tied}
    for row in rows:
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(row['name'])}(?![A-Za-z0-9_])", text, re.I):
            names.add(row["name"])
    return names


def _not_applicable(entry: dict) -> dict:
    return {str(n.get("component") or "").strip().casefold(): n for n in entry.get("not_applicable") or [] if isinstance(n, dict)}


def v13(reports: dict, extract: dict, tree, facts: dict | None) -> tuple[list, list, list, dict]:
    """(errors, warnings, gap items, counts)."""
    errors, warnings, gaps = [], [], []
    rows = components.catalog_rows(reports.get("components") or {})
    counts = {"v13": 0, "v13_not_applicable": 0}
    if not rows:
        return errors, warnings, gaps, counts
    lines = components.file_lines(facts or {})
    size = {r["name"]: 0 for r in rows}
    for p in components.source_files(tree, extract):
        owner = components.component_of(p, rows)[0]
        if owner:
            size[owner] += lines.get(p, 0)
    titles = candidates.card_titles()
    entry_components = {components.component_of(e["path"], rows)[0] for e in (extract or {}).get("entry_points", []) if e.get("path")} - {None}
    for rid, rep in sorted(reports.items()):
        for entry in (rep or {}).get("cards") or []:
            cid = entry.get("card") if isinstance(entry, dict) else None
            if cid not in CARDS or "blocks" not in entry and "entries" not in entry:
                continue  # missing, na or pending: V6 reports it
            na = _not_applicable(entry)
            seen = touched(entry, rows)
            title = titles.get(cid, cid)
            for n in na.values():
                if not str(n.get("reason") or "").strip():
                    errors.append(f"V13: {title} lists {n.get('component')} as not applicable without a reason.")
                else:
                    counts["v13_not_applicable"] += 1
                    gaps.append({"kind": "assumption", "report": rid,
                                 "statement": f"{title} does not cover {n.get('component')}: {str(n['reason']).strip()}",
                                 "how_to_confirm": f"Check that {n.get('component')} really has nothing for the card {title}."})
            for r in rows:
                if r["name"] in seen or r["name"].casefold() in na:
                    continue
                big = size.get(r["name"], 0) > ERROR_LINES
                msg = (f"V13: {title} never mentions the component {r['name']} ({size.get(r['name'], 0)} source lines). Add a row that cites its "
                       f"files, or list it in 'not_applicable' with a reason.")
                (errors if big else warnings).append(msg)
            if cid == "interactions.flows":
                for name in sorted(c for c in entry_components - seen if c.casefold() not in na):
                    errors.append(f"V13: {title} has no flow for the component {name}, which holds an entry point. Add a flow, or list it in 'not_applicable' with a reason.")
    counts["v13"] = sum(1 for x in errors if x.startswith("V13"))
    return errors, warnings, gaps, counts

