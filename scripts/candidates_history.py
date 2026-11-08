"""The extra sections of `dossier candidates` for reports 10, 13 and 14: suggestions computed from `extract/history.json`.

Nothing here is a decision. Tool findings that need a decision (the markers) are listed by `candidates` itself.
"""
from __future__ import annotations

import re

import components
import measured_people
import scip_read

TOP_QUARTER = 4
SOLE_OWNER = 80
OLD_WORDS = {"legacy", "deprecated", "old", "v1", "v2"}


def _items(extract, kind):
    return [i for i in extract.get("history", []) if i.get("kind") == kind]


def _words(name):
    return {w.lower() for w in re.split(r"[^A-Za-z0-9]+|(?<=[a-z])(?=[A-Z])", name) if w}


def _bulk(extract):
    return [f"{b['sha'][:8]}  {b['date']}  {b['files']} files  {b['author']}  {b['subject']}" for b in _items(extract, "bulk")]


def _old_names(extract, tree):
    files = components.source_files(tree, extract)
    names = [f"{p}  (file)" for p in files if _words(p.rsplit("/", 1)[-1].rsplit(".", 1)[0]) & OLD_WORDS]
    names += [f"{s['path']}:{s.get('line', '')}  {s['name']}  (name)" for s in extract.get("symbols", [])
              if s.get("kind") == "def" and _words(s.get("name") or "") & OLD_WORDS]
    return names


def _top_level(symbol):
    """True for a name declared at the top of its file: no local variable, object key or class member."""
    if symbol.startswith("local "):
        return False
    return sum(suffix not in ("/", ":") for _, suffix in scip_read.descriptors(symbol)) == 1


def _duplicate_names(extract):
    where: dict = {}
    for s in extract.get("symbols", []):
        name = s.get("name") or ""
        if s.get("kind") == "def" and name and not name.startswith(("__", "test")) and _top_level(s.get("symbol") or ""):
            where.setdefault(name, set()).add(s["path"])
    return [f"{n}  in {len(p)} files: {', '.join(sorted(p))}" for n, p in sorted(where.items()) if len(p) > 1]


def _squash(name):
    return re.sub(r"[\W_]+", "", name.lower())


def _duplicates(people):
    out = []
    for i, a in enumerate(people):
        for b in people[i + 1:]:
            x, y = _squash(a["name"]), _squash(b["name"])
            if x and y and (x == y or x in y or y in x):
                out.append(f"{a['name']}  /  {b['name']}")
    return out


def _people(extract):
    return [f"{p['name']}  ({p['type']}): {p['commits']} commits, {p['commits_12m']} in the last 12 months, {p.get('owned_commits', 0)} owned, "
            f"{p['first']} to {p['last']}" for p in sorted(_items(extract, "person"), key=lambda p: (-p["commits"], p["name"]))]


def _per_component(extract, catalog):
    ctx = {"extract": extract, "catalog": catalog}
    names, out = measured_people.names_of(ctx), []
    for comp, s in measured_people.component_stats(ctx).items():
        who = sorted(set(s["owned"]) | set(s["lines"]) | set(s["commits"]),
                     key=lambda i: (-s["owned"].get(i, 0), -s["lines"].get(i, 0), -s["commits"].get(i, 0), i))
        out.append(f"{comp}  ({s['files']} files{', some without line data' if s['approx'] else ''})")
        out += [f"    {names.get(i, i.split('@')[0])}: {s['owned'].get(i, 0)} lines owned, {s['lines'].get(i, 0)} lines authored, "
                f"{s['commits'].get(i, 0)} commits" for i in who]
    return out


def _agent_markers(extract):
    return [f"{a['name']}: {a['commits']} human commits carry its marker, in {len(a.get('files') or {})} files" for a in _items(extract, "assistant")]


def _sole_owner_hotspots(extract, tree):
    files = {f["path"]: f for f in _items(extract, "file")}
    ranked = sorted((files[p] for p in components.source_files(tree, extract) if p in files and files[p]["commits_12m"] > 0),
                    key=lambda f: (-f["commits_12m"], f["path"]))
    names = measured_people.names_of({"extract": extract})
    out = []
    for f in ranked[:max(1, len(ranked) // TOP_QUARTER)]:
        total = sum((f.get("owners") or {}).values())
        if not total:
            continue
        who, n = max(f["owners"].items(), key=lambda kv: (kv[1], kv[0]))
        if 100 * n >= SOLE_OWNER * total:
            out.append(f"{f['path']}  {f['commits_12m']} commits in 12 months; {names.get(who, who.split('@')[0])} owns {round(100 * n / total)}% of its commits")
    return out


def data(rid, extract, reports, catalog, tree):
    """{section title: [lines]} for one report. Empty for reports with no extra sections."""
    if not _items(extract, "meta"):
        return {}
    if rid == "change":
        return {"Decision documents": [i["path"] for i in _items(extract, "decision-doc")],
                "Long commit messages": [f"{c['sha'][:8]}  {c['subject']}  ({c['lines']} lines, {c['files']} files)" for c in _items(extract, "long-commit")],
                "TODO and FIXME counts": [f"{t['path']}  {t['count']}" for t in sorted(_items(extract, "todo"), key=lambda t: (-t["count"], t["path"]))],
                "Old-looking names": _old_names(extract, tree),
                "Same name defined more than once": _duplicate_names(extract),
                "Bulk commits": _bulk(extract)}
    if rid == "contributors":
        rows = components.catalog_rows(catalog) if catalog else components.catalog_rows(reports.get("components"))
        return {"People": _people(extract),
                "Possible duplicates": _duplicates(_items(extract, "person")),
                "Components: who wrote and who changes": _per_component(extract, rows),
                "Bulk commits": _bulk(extract),
                "Agent markers": _agent_markers(extract)}
    if rid == "risks":
        cycles = [g for g in extract.get("graph", []) if g.get("kind") == "cycle"]
        return {"Measured findings that may be risks": [f"{len(cycles)} import cycles", f"{len(extract.get('dead', []))} dead code findings",
                                                        *_sole_owner_hotspots(extract, tree)]}
    return {}


def lines(rid, extract, reports, catalog, tree, only_open):
    """The printed form. `--open` lists what still needs a decision, and these sections never do."""
    if only_open:
        return []
    out = []
    for title, rows in data(rid, extract, reports, catalog, tree).items():
        out.append(f"== {title} ==")
        out += rows or ["(none)"]
    return out
