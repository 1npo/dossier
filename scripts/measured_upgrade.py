"""Upgrade burden (D3): how far the runtime and the main frameworks are from end of life, from a shipped snapshot.

The snapshot is `scripts/eol.json`, refreshed by hand with tests/tools/refresh_eol.py. Products the source does not know
(flask, fastapi, sqlalchemy, pydantic) are simply not listed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import measured_change

SNAPSHOT = Path(__file__).resolve().parent / "eol.json"
PACKAGE_PRODUCTS = {"django": "django", "react": "react", "next": "nextjs"}


def _render():
    import render  # imported late: render imports measured, which imports this module

    return render


def load_snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def _cycle(text):
    m = re.search(r"(\d+)\.(\d+)", text or "")
    return f"{m.group(1)}.{m.group(2)}" if m else None


def _major(text):
    m = re.search(r"\d+", text or "")
    return m.group(0) if m else None


def _cycle_of(product):
    """Django's cycles are `5.2`; those of Node, React and Next are a major number."""
    return _cycle if product == "django" else _major


def _node_pin(ctx):
    """(pinned text, source path) from `.nvmrc`, `.node-version`, then `engines.node` of the first package.json, or (None, None)."""
    read, tree = ctx.get("read"), sorted(ctx.get("tree") or ())
    if read is None:
        return None, None
    for name in (".nvmrc", ".node-version"):
        text = (read(name) or "").strip() if name in tree else ""
        if text and _major(text.splitlines()[0]):
            return text.splitlines()[0], name
    manifests = sorted((p for p in tree if p.rsplit("/", 1)[-1] == "package.json"), key=lambda p: (p.count("/"), p))
    if manifests:
        try:
            engines = (json.loads(read(manifests[0]) or "{}").get("engines") or {}).get("node")
        except (ValueError, AttributeError):
            engines = None
        if isinstance(engines, str) and _major(engines):
            return f"engines.node {engines}", manifests[0]
    return None, None


def _gap(cycles, cycle, today):
    entry = next((c for c in cycles if c["cycle"] == cycle), None)
    if not entry or not entry.get("eol"):
        return "not in the data", entry
    return (f"end of life since {entry['eol']}" if entry["eol"] <= today else f"supported until {entry['eol']}"), entry


def rows(ctx, snapshot=None):
    """[(name, pinned, latest, gap, source path or None)]."""
    snap = snapshot or load_snapshot()
    facts, read = ctx.get("facts") or {}, ctx.get("read")
    today = (facts.get("repo") or {}).get("commit_date") or snap["as_of"]
    out = []
    pinned, source = None, None
    version_file = read(".python-version") if read else None
    manifests = facts.get("manifests") or []
    if version_file and _cycle(version_file):
        pinned, source = version_file.strip().splitlines()[0], ".python-version"
    else:
        for m in manifests:
            req = (m.get("extra") or {}).get("requires-python")
            if req and _cycle(req):
                pinned, source = f"requires-python {req}", m["path"]
                break
    if pinned and "python" in snap["products"]:
        cycles = snap["products"]["python"]
        gap, _ = _gap(cycles, _cycle(pinned), today)
        newest = cycles[0]
        out.append(("Python", pinned, f"{newest['latest']} (latest)", gap, source))
    node, node_source = _node_pin(ctx)
    if node and "nodejs" in snap["products"]:
        cycles = snap["products"]["nodejs"]
        gap, _ = _gap(cycles, _major(node), today)
        out.append(("Node.js", node, f"{cycles[0]['latest']} (latest)", gap, node_source))
    deps = (facts.get("dependencies") or {}).get("deps") or []
    seen = set()
    for d in sorted(deps, key=lambda d: d["n"]):
        product = PACKAGE_PRODUCTS.get(d["n"].lower())
        cycle = _cycle_of(product)(d.get("v")) if product else None
        if not product or product not in snap["products"] or not cycle or (d["n"], d.get("v")) in seen:
            continue
        seen.add((d["n"], d.get("v")))
        cycles = snap["products"][product]
        gap, _ = _gap(cycles, cycle, today)
        src = next((m["path"] for m in manifests if any(x.get("name", "").lower() == d["n"].lower() for x in m["dependencies"])), None)
        out.append((d["n"], d["v"], f"{cycles[0]['latest']} (latest)", gap, src))
    return out


def card(cid, ctx, refs):
    if not measured_change.has_history(ctx) and not (ctx.get("facts") or {}).get("manifests"):
        return None
    r = _render()
    snap = load_snapshot()
    caption = measured_change.foot_notes(f"Data as of {snap['as_of']}, from endoflife.date.")
    found = rows(ctx, snap)
    if not found:
        return measured_change.none_found("No runtime or package with end-of-life data was found.") + caption
    cells = [[r.E(n), r.E(p), r.E(l), r.E(g), r.source_cell(refs, (s, None)) if s else ""] for n, p, l, g, s in found]
    return r.render_table(["Runtime or package", "Pinned", "Latest or supported", "Gap", "Source"], cells, refs, "t-change-upgrade-burden", plain=True) + caption


DRAWN = {"change.upgrade-burden": card}
