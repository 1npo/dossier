"""Candidate findings from the extractors: stable ids, groups and loading `extract/*.json`.

Every tool finding that a report must decide about (kept, merged or dismissed) gets an id that survives line
shifts. Standard library only: `adapters` imports this module.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from components import catalog_edges, catalog_rows, component_candidates, component_of, file_lines, parse_paths, source_files  # noqa: F401

ID_OUTPUTS = {"entry_points": "ep", "io_candidates": "io", "models": "md", "dead": "dd", "blindspots": "bs"}


def norm(s: str) -> str:
    """Collapse runs of whitespace to one space and strip."""
    return re.sub(r"\s+", " ", s or "").strip()


def _sha(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def _rule(item: dict) -> str:
    return item.get("rule") or item.get("kind") or ""


def _sort_key(item: dict) -> tuple:
    return (item.get("path", ""), item.get("line") or 0, _rule(item), item.get("name") or "")


def sort_items(items: list) -> list:
    """Items in the order every `extract/*.json` list uses: (path, line, rule or kind, name)."""
    return sorted(items, key=_sort_key)


def assign_ids(output: str, items: list) -> list:
    """Return new item dicts with `id` and `group` (D2), sorted by (path, line, rule or kind, name)."""
    prefix = ID_OUTPUTS[output]
    ordered = sort_items(items)
    seen: dict = {}
    result = []
    for it in ordered:
        rule = _rule(it)
        snippet = it["snippet"] if it.get("snippet") else it.get("name", "")
        key = f"{rule}\0{it['path']}\0{norm(snippet)}"
        n = seen.get(key, 0)
        seen[key] = n + 1
        ident = _sha(key + "\0" + str(n))
        group = _sha(rule + "\0" + it["path"])
        result.append({**it, "id": prefix + "-" + ident, "group": prefix + "g-" + group})
    return result


def load(out) -> dict:
    """{output: items of every adapter, in adapter-name order}. Outputs with no file are left out."""
    loaded = {}
    for f in sorted((Path(out) / "extract").glob("*.json")):
        o = f.stem
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        loaded[o] = [it for name in sorted(data.get("adapters", {})) for it in data["adapters"][name].get("items", [])]
    return loaded


def by_id(extract: dict) -> dict:
    """Item ids and group ids -> item (a group maps to its first item)."""
    found = {}
    for items in extract.values():
        for it in items:
            if "id" in it:
                found[it["id"]] = it
                found.setdefault(it["group"], it)
    return found


def group_members(extract: dict) -> dict:
    """Group id -> the ids of its items."""
    members: dict = {}
    for items in extract.values():
        for it in items:
            if "id" in it:
                members.setdefault(it["group"], []).append(it["id"])
    return members


# ------------------------------------------------------------------ which card owns which finding (D3)

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "prompts" / "schema"
CATEGORY_CARD = {
    "cli-args": "io.inputs", "env-var": "io.inputs", "config-file": "io.inputs", "file-read": "io.inputs", "stdin": "io.inputs",
    "message-consume": "io.inputs", "db-connect": "data.stores", "db-access": "interactions.state",
    "global-state": "interactions.state", "cache": "interactions.state", "thread": "interactions.concurrency",
    "async": "interactions.concurrency", "process-pool": "interactions.concurrency", "lock": "interactions.concurrency",
    "queue": "interactions.concurrency", "stdout": "io.outputs", "file-write": "io.outputs", "outbound-call": "io.outputs",
    "message-produce": "io.outputs", "exit-code": "io.outputs", "error-response": "io.outputs", "log": "behavior.observability",
    "metric": "behavior.observability", "trace": "behavior.observability", "retry": "behavior.failures",
    "timeout": "behavior.failures", "catch-all": "behavior.failures", "transaction": "behavior.failures",
}
DECIDED_OUTPUTS = ("entry_points", "io_candidates", "models")


def card_titles() -> dict:
    """Card id -> title, from prompts/schema/*.json."""
    titles = {}
    for f in sorted(SCHEMA_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            for c in data.get("cards", []) if isinstance(data, dict) else []:  # questions.json is a list, not a report
                titles[c["id"]] = c["title"]
        except (ValueError, KeyError, TypeError):
            continue
    return titles


def home_card(output: str, item: dict):
    if output == "entry_points":
        return "entry.catalog"
    if output == "io_candidates":
        return CATEGORY_CARD.get(item.get("category"))
    if output == "models" and item.get("kind") != "migration":
        return "data.entities"
    return None


def for_report(rid: str, extract: dict) -> dict:
    """Home card id -> its candidate items, for the cards of report `rid`."""
    found: dict = {}
    for output in DECIDED_OUTPUTS:
        for it in extract.get(output, []):
            card = home_card(output, it)
            if card and card.split(".")[0] == rid and "id" in it:
                found.setdefault(card, []).append(it)
    return found


def dispositions(reports: dict) -> dict:
    """Candidate or group id -> [(report id, card id, "kept" | "dismissed")] from `cand` and `dismissed` in the card files."""
    found: dict = {}

    def add(ids, rid, card, how):
        for i in ids or []:
            found.setdefault(i, []).append((rid, card, how))

    for rid, rep in reports.items():
        for entry in (rep or {}).get("cards", []):
            card = entry.get("card")
            for block in entry.get("blocks", []):
                for row in block.get("rows", []) if isinstance(block, dict) else []:
                    add(row.get("cand"), rid, card, "kept")
            add(entry.get("cand"), rid, card, "kept")
            for item in entry.get("entries", []):
                add(item.get("cand"), rid, card, "kept")
            for d in entry.get("dismissed", []):
                add(d.get("cand"), rid, card, "dismissed")
    return found


def open_items(rid: str, extract: dict, reports: dict) -> list:
    """Candidates of the home cards of `rid` that no report keeps, merges or dismisses (by id or group id)."""
    decided = dispositions(reports)
    return [{**it, "card": card} for card, items in sorted(for_report(rid, extract).items()) for it in items
            if it["id"] not in decided and it["group"] not in decided]


# ------------------------------------------------------------------ the `dossier candidates` view


def _group(items: list) -> list:
    groups: dict = {}
    for it in items:
        groups.setdefault(it["group"], []).append(it)
    return [{"group": g, "rule": v[0].get("rule") or v[0].get("kind"), "path": v[0]["path"],
             "hits": [{"id": i["id"], "line": i.get("line"), "end_line": i.get("end_line"), "snippet": i.get("snippet") or i.get("name", "")}
                      for i in sorted(v, key=lambda i: i.get("line") or 0)]}
            for g, v in sorted(groups.items(), key=lambda kv: (kv[1][0]["path"], kv[1][0].get("rule") or "", kv[0]))]


def report_data(rid: str, extract: dict, reports: dict, facts: dict, *, only_open: bool = False, catalog=None, tree=None) -> dict:
    """The data behind `dossier candidates --report RID`."""
    titles = card_titles()
    data: dict = {"report": rid, "cards": []}
    open_ids = {i["id"] for i in open_items(rid, extract, reports)}
    for card, items in sorted(for_report(rid, extract).items()):
        shown = [i for i in items if not only_open or i["id"] in open_ids]
        if shown:
            data["cards"].append({"card": card, "title": titles.get(card, card), "findings": len(shown), "groups": _group(shown)})
    if rid == "components":
        data["components"] = component_candidates(tree, extract, facts)
        if catalog is not None:
            rows, files = catalog_rows(catalog), source_files(tree, extract)
            lines = file_lines(facts)
            data["catalog"] = {
                "components": [{"name": r["name"], "files": sum(component_of(p, rows)[0] == r["name"] for p in files),
                                "lines": sum(lines.get(p, 0) for p in files if component_of(p, rows)[0] == r["name"])} for r in rows],
                "edges": catalog_edges(rows, extract),
                "unassigned": [p for p in files if component_of(p, rows)[0] is None]}
    if rid == "reading":
        import graphs

        mods = [g for g in extract.get("graph", []) if g.get("kind") == "module"]
        rank = graphs.pagerank([m["module"] for m in mods], [(g["from"], g["to"]) for g in extract.get("graph", []) if g.get("kind") == "import"])
        data["modules"] = [{"module": m["module"], "path": m["path"], "rank": round(rank.get(m["module"], 0), 4)}
                           for m in sorted(mods, key=lambda m: (-rank.get(m["module"], 0), m["module"]))[:30]]
        data["entry_points"] = sorted({e["path"] for e in extract.get("entry_points", [])})
        data["tests"] = sorted({t["path"] for t in extract.get("tests", []) if t.get("kind") == "test-file"})
    return data


def text(rid: str, extract: dict, reports: dict, facts: dict, *, only_open: bool = False, catalog=None, tree=None) -> str:
    d = report_data(rid, extract, reports, facts, only_open=only_open, catalog=catalog, tree=tree)
    out = []
    for card in d["cards"]:
        out.append(f"== {card['card']} ({card['title']}): {card['findings']} findings in {len(card['groups'])} groups ==")
        for g in card["groups"]:
            lines = ", ".join(str(h["line"]) for h in g["hits"])
            out.append(f"{g['group']}  {g['rule']}  {g['path']}  ({len(g['hits'])} hits: lines {lines})")
            out += [f"    {h['id']}  {g['path']}:{h['line']}  {h['snippet']}" for h in g["hits"]]
    if "components" in d:
        c = d["components"]
        out.append("== Folders with source files ==")
        out += [f"{f['path']}  ({f['files']} files, {f['lines']} lines)" for f in c["folders"]]
        out.append("== Python packages ==")
        out += [f"{p['package']}  ({p['modules']} modules)" for p in c["packages"]]
        out.append("== Import communities (folders that import each other most) ==")
        out += [f"{x['label']}: {', '.join(x['folders'])}" for x in c["communities"]]
    if "catalog" in d:
        k = d["catalog"]
        out.append("== Drafted components: size ==")
        out += [f"{x['name']}  ({x['files']} files, {x['lines']} lines)" for x in k["components"]]
        out.append("== Drafted components: imports between them ==")
        out += [f"{e['from']} -> {e['to']}  ({e['imports']} imports)" for e in k["edges"]]
        out.append(f"== Source files in no component: {len(k['unassigned'])} ==")
        out += k["unassigned"]
    if "modules" in d:
        out.append("== Most imported modules (top 30) ==")
        out += [f"{m['module']}  {m['path']}  (rank {m['rank']})" for m in d["modules"]]
        out.append("== Entry point files ==")
        out += d["entry_points"]
        out.append("== Test files ==")
        out += d["tests"]
    return "\n".join(out) + ("\n" if out else "")
