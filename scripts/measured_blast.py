"""Blast radius (D5): what depends on a file, precomputed here and picked in the browser.

The closure is stored as one bitset per file, so the page needs no graph code and the table keeps its numbers without JavaScript.
"""
from __future__ import annotations

import base64
import json
import re

import components
import graphs
import measured_change


def _render():
    import render  # imported late: render imports measured, which imports this module

    return render


def _bits(indexes, n):
    raw = bytearray((n + 7) // 8)
    for j in indexes:
        raw[j >> 3] |= 1 << (j & 7)
    return base64.b64encode(bytes(raw)).decode()


def data(ctx) -> dict | None:
    extract = ctx.get("extract") or {}
    graph = [g for g in extract.get("graph", []) if g.get("kind") == "module"]
    source = components.source_files(ctx.get("tree"), extract)
    files = sorted(set(source) | {g["path"] for g in graph})
    if not files:
        return None
    pos = {p: i for i, p in enumerate(files)}
    in_graph = {g["path"] for g in graph}
    edges = {(g["path"], p) for g in extract.get("graph", []) if g.get("kind") == "import" for p in g.get("paths") or [] if p != g["path"]}
    closure = graphs.reverse_closure(sorted(in_graph), sorted(edges))
    catalog = ctx.get("catalog") or []
    names = sorted(c["name"] for c in catalog)
    tests = sorted(t["path"] for t in extract.get("tests", []) if t.get("kind") == "test-file")
    tpos = {p: i for i, p in enumerate(tests)}
    ft = [[] for _ in files]
    for t in extract.get("tests", []):
        if t.get("kind") == "test-file":
            for p in t.get("paths") or []:
                if p in pos:
                    ft[pos[p]].append(tpos[t["path"]])
    co: dict = {}
    for p in measured_change.history_items(ctx, "pair"):
        if p["co_commits"] >= measured_change.COCHANGE_MIN:
            co.setdefault(p["a"], []).append([p["b"], p["co_commits"]])
            co.setdefault(p["b"], []).append([p["a"], p["co_commits"]])
    for v in co.values():
        v.sort(key=lambda x: (-x[1], x[0]))
    direct = [sum(1 for a, b in edges if b == p) if p in in_graph else 0 for p in files]
    return {"files": files, "graph": [int(p in in_graph) for p in files],
            "component": [names.index(components.component_of(p, catalog)[0]) if catalog and components.component_of(p, catalog)[0] in names else -1 for p in files],
            "components": names,
            "dep": [_bits([pos[d] for d in closure[p] if d in pos], len(files)) if p in in_graph else "" for p in files],
            "direct": direct, "tests": tests, "ft": ft, "co": co}


def _popcount(b64):
    return sum(bin(x).count("1") for x in base64.b64decode(b64)) if b64 else 0


def _dependents(d, i):
    raw = base64.b64decode(d["dep"][i]) if d["dep"][i] else b""
    return [j for j in range(len(d["files"])) if j >> 3 < len(raw) and raw[j >> 3] & (1 << (j & 7))]


def blast(cid, ctx, refs):
    d = data(ctx)
    if d is None:
        return None
    r = _render()
    extract = ctx.get("extract") or {}
    blind = len([b for b in extract.get("blindspots", [])])
    rows = []
    for i, p in enumerate(d["files"]):
        if d["graph"][i]:
            deps = _dependents(d, i)
            tset = set(d["ft"][i]).union(*[d["ft"][j] for j in deps]) if deps else set(d["ft"][i])
            direct, alld = (str(d["direct"][i]), d["direct"][i]), (str(len(deps)), len(deps))
        else:
            tset = set(d["ft"][i])
            direct = alld = ("not in the graph", -1)
        comp = d["components"][d["component"][i]] if d["component"][i] >= 0 else "-"
        rows.append([r.path_code(p), r.E(comp), direct, alld, (str(len(tset)), len(tset)), (str(len(d["co"].get(p, []))), len(d["co"].get(p, [])))])
    table = r.render_table(["File", "Component", "Direct dependents", "All dependents", "Importing tests", "Co-changing files"], rows, refs,
                           "t-change-blast-radius", plain=True)
    it = iter(range(len(rows)))
    table = re.sub(r"<tr>(?=<td)", lambda m: f'<tr data-file="{next(it)}">', table)
    opts_c = "".join(f'<option value="c{i}">{r.E(n)}</option>' for i, n in enumerate(d["components"]))
    opts_f = "".join(f'<option value="{i}">{r.E(p)}</option>' for i, p in enumerate(d["files"]))
    picker = ('<div class="blast-picker"><label for="blast-pick">Pick a component or a file</label> '
              f'<select id="blast-pick" class="input"><option value="">Choose...</option>'
              + (f'<optgroup label="Components">{opts_c}</optgroup>' if opts_c else "") + f'<optgroup label="Files">{opts_f}</optgroup></select></div>')
    out = ('<div id="blast-out" class="blast-lists" aria-live="polite">'
           '<div><h4>Depend on it (<span id="blast-n-dependents">0</span>)</h4><ul id="blast-dependents" class="blast-list"></ul></div>'
           '<div><h4>Tests that reach it (<span id="blast-n-tests">0</span>)</h4><ul id="blast-tests" class="blast-list"></ul></div>'
           '<div><h4>Change with it (<span id="blast-n-co">0</span>)</h4><ul id="blast-co" class="blast-list"></ul></div></div>')
    if extract.get("graph"):
        note = f"Built from static imports. {blind} places that load code at run time are not in this graph (see Gaps)."
    else:
        note = "No import graph was extracted, so only co-changing files are shown."
    blob = json.dumps(d, separators=(",", ":")).replace("</", "<\\/")
    return picker + out + table + f'<p class="muted">{r.E(note)}</p><script type="application/json" id="blast-data">{blob}</script>'


DRAWN = {"change.blast-radius": blast}
