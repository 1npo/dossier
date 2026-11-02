"""Card schema: load prompts/schema/*.json, lint them, and check a report against its schema (V6)."""
import json
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "prompts" / "schema"
ALLOW_PENDING = False  # every card of a report Claude writes must be filled; only migration (allow_pending=True) may leave one pending
REPORT_ORDER = ("dossier", "overview", "reading", "entry", "components", "interactions", "io", "data",
                "behavior", "change", "conventions", "ops", "contributors", "risks", "gaps", "corrections")
QUESTIONS_FILE = "questions.json"  # question list for the dossier.questions card; not a report schema

TIERS = ("M", "A", "R", "M+A")
SHAPES = ("blocks", "flows", "entries", "computed")
SLOT_TYPES = ("table", "text", "list", "diagram")
ENTRY_KEYS = {"card", "title", "blocks", "entries", "na", "cite", "pending", "dismissed", "unassigned"}


def load(rid, schema_dir=SCHEMA_DIR):
    if rid == Path(QUESTIONS_FILE).stem:
        return None
    p = Path(schema_dir) / f"{rid}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def load_all(schema_dir=SCHEMA_DIR):
    out = {}
    for p in sorted(Path(schema_dir).glob("*.json")):
        if p.name == QUESTIONS_FILE:
            continue
        out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    return out


def load_questions(schema_dir=SCHEMA_DIR):
    p = Path(schema_dir) / QUESTIONS_FILE
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def lint(sch):
    errs, seen = [], set()
    rid = sch.get("report", "?")
    for c in sch.get("cards", []):
        cid = c.get("id", "?")
        w = f"{rid}: card {cid}"
        if not str(cid).startswith(rid + "."):
            errs.append(f"{w}: id must start with '{rid}.'")
        if cid in seen:
            errs.append(f"{w}: duplicate id")
        seen.add(cid)
        if c.get("tier") not in TIERS:
            errs.append(f"{w}: bad tier")
        if "informational" in c and not isinstance(c["informational"], bool):
            errs.append(f"{w}: informational must be a boolean")
        if c.get("priority") not in ("P0", "P1"):
            errs.append(f"{w}: bad priority")
        if c.get("writer") not in ("claude", "script"):
            errs.append(f"{w}: bad writer")
        shape = c.get("shape")
        if shape not in SHAPES:
            errs.append(f"{w}: unknown shape")
        want = "script" if (c.get("tier") == "M" or shape == "computed") else "claude"
        if c.get("writer") != want:
            errs.append(f"{w}: writer must be {want}")
        if shape == "blocks":
            slots = c.get("slots")
            if not slots:
                errs.append(f"{w}: blocks shape needs slots")
            for s in slots or []:
                if s.get("type") not in SLOT_TYPES:
                    errs.append(f"{w}: unknown slot type")
                if s.get("type") == "table" and not s.get("columns"):
                    errs.append(f"{w}: table slot needs columns")
        if shape == "entries" and not (c.get("key") and c.get("fields")):
            errs.append(f"{w}: entries shape needs key and fields")
        for fk in ("fixed", "fixed2"):
            f = c.get(fk)
            if f is not None and not (isinstance(f, dict) and f.get("on") and f.get("values")):
                errs.append(f"{w}: {fk} must be null or have on and values")
    return errs


def _norm(s):
    return str(s).replace("`", "").strip().lower()


def _slot_max(s):
    return s["max"] if "max" in s else 1


def _check_blocks(w, card, blocks, errs, warns):
    if not isinstance(blocks, list):
        errs.append(f"V6: {w}: 'blocks' must be a list")
        return
    i = 0
    tables = []
    for s in card["slots"]:
        mx, mn, n = _slot_max(s), s.get("min", 1), 0
        while i < len(blocks) and isinstance(blocks[i], dict) and blocks[i].get("type") == s["type"] and (mx is None or n < mx):
            b = blocks[i]
            if s["type"] == "table":
                if b.get("columns") != s["columns"]:
                    errs.append(f"V6: {w}: table columns must be {s['columns']}, found {b.get('columns')}")
                elif not b.get("rows"):
                    errs.append(f"V6: {w}: table has no rows; use 'na' with a reason and a citation")
                tables.append(b)
            n, i = n + 1, i + 1
        if n < mn:
            errs.append(f"V6: {w}: missing block of type {s['type']}")
    if i < len(blocks):
        t = blocks[i].get("type") if isinstance(blocks[i], dict) else type(blocks[i]).__name__
        errs.append(f"V6: {w}: unexpected block {i + 1} ({t})")
    tix = [n for n, s in enumerate(card["slots"]) if s["type"] == "table"]
    for fk, k in (("fixed", 0), ("fixed2", 1)):
        f = card.get(fk)
        if f and k < len(tables):
            col = card["slots"][tix[k]]["columns"]
            if f["on"] in col:
                j = col.index(f["on"])
                have = {_norm(r["cells"][j]) for r in tables[k].get("rows", []) if isinstance(r, dict) and len(r.get("cells", [])) > j}
                _fixed_warn(w, f, have, warns)


def _fixed_warn(w, f, have, warns):
    for v in f["values"]:
        if _norm(v) not in have:
            warns.append(f"V6: {w}: has no row for '{v}'")


def _check_flows(w, card, blocks, errs):
    if not isinstance(blocks, list) or not blocks or not isinstance(blocks[0], dict) or blocks[0].get("type") != "diagram":
        errs.append(f"V6: {w}: flows must start with a diagram block")
        return
    nd, prev = 0, None
    for n, b in enumerate(blocks, 1):
        t = b.get("type") if isinstance(b, dict) else None
        if t == "diagram":
            nd += 1
        elif t in ("text", "list") and prev == "diagram":
            pass
        else:
            errs.append(f"V6: {w}: unexpected block {n} ({t})")
        prev = t
    mx = card.get("max_diagrams")
    if mx and nd > mx:
        errs.append(f"V6: {w}: at most {mx} diagram allowed")


def _check_entries(w, card, entries, errs, warns):
    if not isinstance(entries, list) or not entries:
        errs.append(f"V6: {w}: 'entries' must be a non-empty list")
        return
    ids = [f["id"] for f in card["fields"]]
    names = set()
    for n, e in enumerate(entries, 1):
        ok = isinstance(e, dict) and isinstance(e.get(card["key"]), str) and e[card["key"]].strip()
        if not ok:
            errs.append(f"V6: {w}: entry {n} needs a non-empty '{card['key']}'")
            continue
        names.add(_norm(e[card["key"]]))
        fl = e.get("fields")
        if not isinstance(fl, dict) or set(fl) != set(ids):
            errs.append(f"V6: {w}: entry {n} fields must be exactly {ids}")
        elif any(not isinstance(v, str) or not v.strip() for v in fl.values()):
            errs.append(f"V6: {w}: entry {n} fields must be non-empty text")
    if card.get("fixed"):
        _fixed_warn(w, card["fixed"], names, warns)


def validate(rid, rep, sch, allow_pending=None):
    allow_pending = ALLOW_PENDING if allow_pending is None else allow_pending
    errs, warns = [], []
    if not isinstance(rep, dict):
        return [f"V6: report {rid} must be a JSON object"], []
    cards = sch.get("cards", [])
    if not any(c["writer"] == "claude" for c in cards) and "cards" not in rep:
        return [], []
    if "cards" not in rep:
        if isinstance(rep.get("blocks"), list):
            return [f"V6: report {rid} uses the old layout ('blocks' without 'cards'). Run: dossier.py migrate"], []
        return [f"V6: report {rid} needs a 'cards' list"], []
    if not isinstance(rep["cards"], list):
        return [f"V6: report {rid}: 'cards' must be a list"], []
    index = {c["id"]: n for n, c in enumerate(cards)}
    ptr, seen = 0, set()

    def required_between(lo, hi):
        for c in cards[lo:hi]:
            if c["writer"] == "claude" and c["id"] not in seen:
                errs.append(f"V6: {rid}: required card {c['id']} is missing")

    for entry in rep["cards"]:
        if not isinstance(entry, dict) or "card" not in entry:
            errs.append(f"V6: {rid}: a card entry needs a 'card' id")
            continue
        cid = entry["card"]
        w = f"{rid}: card {cid}"
        if cid not in index:
            errs.append(f"V6: {w}: unknown card")
            continue
        if cid in seen:
            errs.append(f"V6: {w}: appears more than once")
            continue
        if index[cid] < ptr:
            errs.append(f"V6: {w}: out of order")
            seen.add(cid)
            continue
        seen.add(cid)
        required_between(ptr, index[cid])
        ptr = index[cid] + 1
        card = cards[index[cid]]
        extra = set(entry) - ENTRY_KEYS
        if extra:
            errs.append(f"V6: {w}: unknown keys {sorted(extra)}")
        if "title" in entry and entry["title"] != card["title"]:
            errs.append(f"V6: {w}: title must be '{card['title']}'")
        content = {k for k in ("blocks", "entries", "na", "pending") if k in entry}
        if card["writer"] == "script":
            if content != {"pending"} or set(entry) - {"card", "title", "pending"}:
                errs.append(f"V6: {w}: is produced by a script and must not be written")
            elif entry["pending"] is not True or not allow_pending:
                errs.append(f"V6: {w}: pending is not allowed")
            continue
        if "pending" in entry:
            if entry["pending"] is not True or not allow_pending:
                errs.append(f"V6: {w}: pending is not allowed")
            elif content != {"pending"}:
                errs.append(f"V6: {w}: pending excludes other content")
            continue
        if "na" in entry:
            cite = entry.get("cite")
            if not isinstance(entry["na"], str) or not entry["na"].strip() or "blocks" in entry or "entries" in entry:
                errs.append(f"V6: {w}: 'na' must be a reason text and nothing else")
            elif not (isinstance(cite, list) and cite and all(isinstance(x, str) for x in cite)):
                errs.append(f"V6: {w}: 'na' needs a non-empty cite list")
            continue
        shape = card["shape"]
        want = "entries" if shape == "entries" else "blocks"
        other = "blocks" if want == "entries" else "entries"
        if want not in entry or other in entry:
            errs.append(f"V6: {w}: needs exactly '{want}' (or 'na', or 'pending')")
        elif shape == "blocks":
            _check_blocks(w, card, entry["blocks"], errs, warns)
        elif shape == "flows":
            _check_flows(w, card, entry["blocks"], errs)
        else:
            _check_entries(w, card, entry["entries"], errs, warns)
    required_between(ptr, len(cards))
    return errs, warns
