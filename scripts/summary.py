"""`summary.json`: the machine-readable summary written next to the page (spec section 9, plan 009 D10).

Everything here comes from structures the reports and extractors already hold. No email address is written.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import buildlog
import candidates
import components
import measured_change
import measured_people
import summary_check

FILE = "summary.json"
SEVERITIES = ("critical", "high", "medium", "low", "info")
OWNER_MIN = 20
STATUS = {"ok": "ok", "failed": "partial"}
NOREPLY = re.compile(r"(?:\d+\+)?([^@+]+)@users\.noreply\.github\.com$", re.I)
validate = summary_check.validate
load_schema = summary_check.load_schema


def plain(cell) -> str:
    """A table cell as plain text: citations dropped (their label kept), backticks and surrounding space removed."""
    text = re.sub(r"\[\[([^\]|]*)(?:\|([^\]]*))?\]\]", lambda m: m.group(2) or "", str(cell or ""))
    return re.sub(r"\s+", " ", text.replace("`", "")).strip()


def _slug(name) -> str:
    return re.sub(r"[^a-z0-9]+", "-", plain(name).lower()).strip("-")


def _rows(reports, cid):
    """[(columns, row)] of every table of one card. A not-applicable or missing card gives none."""
    rid = cid.split(".")[0]
    for entry in ((reports or {}).get(rid) or {}).get("cards") or []:
        if isinstance(entry, dict) and entry.get("card") == cid:
            return [(b.get("columns") or [], r) for b in entry.get("blocks") or [] if isinstance(b, dict) for r in b.get("rows") or [] if isinstance(r, dict)]
    return []


def _cell(columns, row, name) -> str:
    cells = row.get("cells") or []
    return str(cells[columns.index(name)]) if name in columns and columns.index(name) < len(cells) else ""


def contributor_id(ident) -> str:
    return "c-" + hashlib.sha256(str(ident).encode("utf-8")).hexdigest()[:12]


def _username(person):
    if person.get("username"):
        return person["username"]
    ident = person["person"]
    if ident.startswith("github:"):
        return ident[7:]
    m = NOREPLY.search(ident)
    return m.group(1) if m else None


def _contributors(extract):
    people = [i for i in extract.get("history", []) if i.get("kind") == "person"]
    rows = [{"id": contributor_id(p["person"]), "kind": p["type"], "name": p["name"].split("@")[0] if "@" in p["name"] else p["name"],
             "username": _username(p)} for p in people]
    by_ident = {a: contributor_id(p["person"]) for p in people for a in (p["person"], *(p.get("aliases") or []))}
    return sorted(rows, key=lambda r: r["id"]), by_ident


def _extractors(tools, extract):
    partial = any(i.get("kind") == "meta" and i.get("status") == "partial" for i in extract.get("history", []))
    return [{"name": t["name"], "version": t["version"], "status": "partial" if t["name"] == "git" and partial and t["status"] == "ok" else STATUS.get(t["status"], "missing")}
            for t in tools]


def _components(reports, extract, facts, tree, owners_of):
    rows = components.catalog_rows((reports or {}).get("components") or {})
    ids = {r["name"]: _slug(r["name"]) for r in rows}
    edges = components.catalog_edges(rows, extract)
    lines, files = components.file_lines(facts), components.source_files(tree, extract)
    stats = measured_people.component_stats({"extract": extract, "catalog": rows})
    out = []
    for r in rows:
        own = stats[r["name"]]["owned"] if r["name"] in stats else {}
        total = sum(own.values())
        by_id: dict = {}
        for ident, n in own.items():
            if ident in owners_of:
                by_id[owners_of[ident]] = by_id.get(owners_of[ident], 0) + n
        out.append({"id": ids[r["name"]], "name": r["name"], "paths": r["paths"],
                    "depends_on": sorted({ids[e["to"]] for e in edges if e["from"] == r["name"]}),
                    "used_by": sorted({ids[e["from"]] for e in edges if e["to"] == r["name"]}),
                    "size": sum(lines.get(p, 0) for p in files if components.component_of(p, rows)[0] == r["name"]),
                    "owners": sorted(c for c, n in by_id.items() if total and 100 * n >= OWNER_MIN * total)})
    return out


def _entry_points(reports, extract):
    found, out = candidates.by_id(extract), []
    for columns, row in _rows(reports, "entry.catalog"):
        hit = next((found[i] for i in row.get("cand") or [] if i in found and found[i].get("path")), None)
        if hit:
            where = f"{hit['path']}:{hit['line']}" if hit.get("line") else hit["path"]
        else:
            where = next(iter(row.get("cite") or []), None)
        out.append({"kind": plain(_cell(columns, row, "Kind")), "name": plain(_cell(columns, row, "Name")),
                    "location": plain(where or _cell(columns, row, "Starts at"))})
    return out


def _contracts(reports):
    out = []
    for columns, row in _rows(reports, "io.contracts"):
        raw = _cell(columns, row, "Schema location")
        m = re.search(r"\[\[([^\]\s:|]+)", raw) or re.search(r"`([^`\s:]+\.[A-Za-z0-9]+)", raw)
        out.append({"name": plain(_cell(columns, row, "Contract")), "direction": plain(_cell(columns, row, "Direction")).lower(),
                    "counterparty": plain(_cell(columns, row, "Counterparty")), "schema_path": m.group(1) if m else None})
    return out


def _dependencies(dependencies):
    scope = lambda d: "dev" if d.get("s") == "dev" else "runtime"  # noqa: E731
    return ([{"name": d["n"], "ecosystem": d.get("ecosystem") or "unknown", "scope": scope(d), "files_importing": d.get("src", 0) + d.get("tst", 0)}
             for d in (dependencies or {}).get("deps") or []]
            + [{"name": d["n"], "ecosystem": d.get("ecosystem") or "unknown", "scope": scope(d), "files_importing": 0}
               for d in (dependencies or {}).get("unused") or []])


def _remote(repo):
    remote = repo.get("remote") or {}
    url = remote.get("web_base") or remote.get("url")
    return re.sub(r"^[^@/]*@", "", url) if url else None


def _ownership(reports, ctx):
    """Bus factor and top owner share (humans only), and the paths of components whose status is `departed`."""
    paths = {c["name"].lower(): c["paths"] for c in ctx["catalog"]}
    departed = {p for columns, row in _rows(reports, "contributors.concentration") if plain(_cell(columns, row, "Status")).lower() == "departed"
                for p in paths.get(plain(_cell(columns, row, "Area")).lower(), [])}
    return {**measured_people.bus_factor(ctx), "at_risk_paths": sorted(departed)}


def build(facts, reports, extract, build_, gap_counts, version, dependencies, tree, tools=None, now=None) -> dict:
    """The summary document. `tools` is `candidates.tool_list(out)`; `build_` is the loaded build.json or None."""
    import render  # late: render imports this module's neighbours

    repo = facts.get("repo") or {}
    tiers = {l["name"]: l.get("tier") for l in ((buildlog.latest(build_, "tools") or {}).get("details") or {}).get("languages") or []} if build_ else {}
    ctx = {"extract": extract, "catalog": components.catalog_rows((reports or {}).get("components") or {}), "tree": tree, "facts": facts}
    people, owners_of = _contributors(extract)
    risk = render.risk_counts((reports or {}).get("risks") or {})[0]
    hot = sorted(({"path": f["path"], "churn": f["commits_12m"]} for f in measured_change.history_items(ctx, "file") if f.get("commits_12m", 0) > 0),
                 key=lambda h: (-h["churn"], h["path"]))
    return {
        "schema_version": 1, "dossier_version": version, "generated_at": now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo": {"name": repo.get("name") or "", "remote": _remote(repo), "branch": repo.get("branch"), "sha": repo.get("sha") or "", "commit_date": repo.get("commit_date")},
        "languages": [{"name": l["name"], "tier": tiers.get(l["name"]) or "B", "share": l.get("share_pct", 0)} for l in facts.get("languages") or [] if l.get("kind") == "code"],
        "extractors": _extractors(tools or [], extract),
        "components": _components(reports, extract, facts, tree, owners_of),
        "entry_points": _entry_points(reports, extract),
        "contributors": people,
        "contracts": _contracts(reports),
        "external_dependencies": _dependencies(dependencies),
        "data_stores": [{"name": plain(_cell(c, r, "Store")), "technology": plain(_cell(c, r, "Technology"))} for c, r in _rows(reports, "data.stores")],
        "risks": {s: risk[s] for s in SEVERITIES},
        "ownership": _ownership(reports, ctx),
        "change": {"hotspots": hot, "cochange_pairs_unlinked": sum(1 for _, v in measured_change.pair_rows(ctx) if v == "no")},
        "gaps": {k: (gap_counts or {}).get(k, 0) for k in ("unknown", "inference", "assumption", "coverage")},
    }


def write(out, doc) -> Path:
    """Write `<out>/summary.json` atomically."""
    path = Path(out) / FILE
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def check_file(out, facts, version) -> list:
    """The problems of the written `summary.json` (V8): missing, unreadable, off its schema, or made at another commit or skill version."""
    path = Path(out) / FILE
    if not path.exists():
        return ["V8: summary.json: the file is missing. Run render."]
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return ["V8: summary.json: the file is not valid JSON. Run render."]
    problems = validate(doc)
    if problems:
        return problems
    if doc["repo"]["sha"] != ((facts or {}).get("repo") or {}).get("sha"):
        problems.append(f"V8: summary.json: $.repo.sha: made at {doc['repo']['sha'][:10]}, not the commit of this dossier. Run render.")
    if doc["dossier_version"] != version:
        problems.append(f"V8: summary.json: $.dossier_version: made by {doc['dossier_version']}, not {version}. Run render.")
    return problems


def remove(out) -> None:
    (Path(out) / FILE).unlink(missing_ok=True)
