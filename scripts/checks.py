"""Checks that compare the reports with the extractor output: V5 (every tool finding has a decision) and, later, V2, V3, V4, V7.

Each check returns `(errors, warnings, gap_items, counts)`. Gaps wording is fixed so item ids stay stable across builds.
"""
from __future__ import annotations

import candidates
import components
import process

FIXED_ROW_CARDS = ("io.inputs", "io.outputs")


def _report_of(card_id: str) -> str:
    return card_id.split(".")[0]


def _nodes(entry: dict) -> list:
    """The table rows and entries of one card entry that can carry `cand` or `added`."""
    rows = [r for b in entry.get("blocks") or [] if isinstance(b, dict) for r in b.get("rows") or [] if isinstance(r, dict)]
    return rows + [e for e in entry.get("entries") or [] if isinstance(e, dict)]


def _cards(reports: dict):
    for rid, rep in sorted(reports.items()):
        for entry in (rep or {}).get("cards") or []:
            if isinstance(entry, dict) and entry.get("card"):
                yield rid, entry["card"], entry


def _as_list(v) -> list:
    return [x for x in v if isinstance(x, str)] if isinstance(v, list) else []


def _tied(item: dict) -> str:
    where = f"{item['path']}:{item['line']}" if item.get("line") else item["path"]
    return f"{item['id']} ({where}, {item.get('rule') or item.get('kind')})"


def v5(reports: dict, extract: dict) -> tuple[list, list, list, dict]:
    """Every candidate in entry_points, io_candidates and entity models is kept, merged or dismissed (D3)."""
    errors, warnings, gaps = [], [], []
    candidates_by_card = {}
    for output in candidates.DECIDED_OUTPUTS:
        for it in extract.get(output, []):
            card = candidates.home_card(output, it)
            if card and "id" in it:
                candidates_by_card.setdefault(card, []).append(it)
    total = sum(len(v) for v in candidates_by_card.values())
    counts = {"v5_candidates": total, "v5_open": 0}
    if not extract:
        return errors, warnings, gaps, counts
    titles = candidates.card_titles()
    known = candidates.by_id(extract)
    members = candidates.group_members(extract)
    kept: dict = {}
    dismissed: dict = {}
    for rid, card, entry in _cards(reports):
        for node in _nodes(entry):
            ids = _as_list(node.get("cand"))
            if ids and node.get("added"):
                errors.append(f"V5: {rid} card {card}: a row says both which tool findings it covers ('cand') and 'added'. Use one.")
            for i in ids:
                kept.setdefault(i, []).append(card)
        for d in entry.get("dismissed") or []:
            ids = _as_list(d.get("cand")) if isinstance(d, dict) else []
            if not ids or not isinstance(d.get("reason"), str) or not d["reason"].strip():
                errors.append(f"V5: {rid} card {card}: every dismissed entry needs the finding ids ('cand') and a reason.")
            for i in ids:
                dismissed.setdefault(i, []).append(card)
        if isinstance(entry.get("cand"), list):
            for i in _as_list(entry["cand"]):
                kept.setdefault(i, []).append(card)
    for i, cards_ in sorted({**kept, **dismissed}.items()):
        if i not in known:
            where = (kept.get(i) or dismissed.get(i))[0]
            errors.append(f"V5: {_report_of(where)} card {where} names {i}, which is not a tool finding in this build.")

    def expand(table):
        out: dict = {}
        for i, cs in table.items():
            for m in members.get(i, [i]):
                out.setdefault(m, []).extend(cs)
        return out
    kept_x, dismissed_x = expand(kept), expand(dismissed)
    for i in sorted(set(kept_x) & set(dismissed_x)):
        errors.append(f"V5: {i} is kept in {kept_x[i][0]} and dismissed in {dismissed_x[i][0]}.")
    decided = set(kept) | set(dismissed)
    open_total = 0
    open_groups: dict = {}
    for card, items in sorted(candidates_by_card.items()):
        left = [it for it in items if it["id"] not in decided and it["group"] not in decided]
        if not left:
            continue
        open_total += len(left)
        shown = [_tied(left[0])] + [it["id"] for it in left[1:5]]
        more = len(left) - len(shown)
        listing = ", ".join(shown) + (f" and {more} more" if more > 0 else "")
        errors.append(f"V5: {len(left)} tool findings for {titles.get(card, card)} have no decision, for example {listing}. Keep, merge or dismiss them.")
        for it in left:
            open_groups.setdefault((card, it["group"]), []).append(it)
    counts["v5_open"] = open_total
    for (card, _), v in sorted(open_groups.items()):
        first = v[0]
        line = f":{first['line']}" if first.get("line") else ""
        gaps.append({"kind": "coverage", "report": _report_of(card),
                     "statement": f"A tool found {len(v)} item(s) for {titles.get(card, card)} in [[{first['path']}{line}]] ({first.get('rule') or first.get('kind')}) that no report accounts for.",
                     "how_to_confirm": "Decide in the report whether to keep, merge or dismiss them, then build again."})
    for rid, card, entry in _cards(reports):
        if card not in candidates_by_card or "blocks" not in entry and "entries" not in entry:
            continue
        for node in _nodes(entry):
            if node.get("cand") or node.get("added"):
                continue
            cells = node.get("cells") or []
            if card in FIXED_ROW_CARDS and node.get("conf") == "confirmed" and len(cells) > 1 and str(cells[1]).strip().lower() == "none":
                continue
            first = cells[0] if cells else ""
            warnings.append(f"V5: {rid} card {card}, row '{first}': say which tool findings it covers ('cand') or mark it 'added'.")
    return errors, warnings, gaps, counts


parse_paths = components.parse_paths


def best_component(path: str, rows: list) -> tuple:
    """(winning component or None, the other components that match equally well). `rows`: [{"name", "paths": [...]}]."""
    return components.component_of(path, rows)


def _entry(reports: dict, card_id: str):
    for _, card, entry in _cards(reports):
        if card == card_id:
            return entry
    return None


def _name(text) -> str:
    return str(text or "").replace("`", "").strip().casefold()


def v4(reports: dict, tree, facts=None) -> tuple[list, list, list, dict]:
    """Every tracked source file belongs to one component, or is listed as unassigned (D4)."""
    errors, warnings, gaps = [], [], []
    counts = {"v4": 0}
    cat = _entry(reports, "components.catalog")
    if not cat or "blocks" not in cat:  # missing, na or pending: V6 reports it
        return errors, warnings, gaps, counts
    rows = components.catalog_rows({"cards": [cat]})
    files = components.source_files(tree, {})
    unassigned = [u for u in cat.get("unassigned") or [] if isinstance(u, dict)]
    covers = [(u, parse_paths(str(u.get("paths", "")))) for u in unassigned]
    free: dict = {i: [] for i in range(len(covers))}
    missing = []
    for path in files:
        owner, tied = best_component(path, rows)
        if owner:
            if tied:
                errors.append(f"V4: {path} belongs to both {owner} and {', '.join(tied[:-1]) + ' and ' + tied[-1] if len(tied) > 1 else tied[0]}.")
            continue
        hit = [i for i, (_, pats) in enumerate(covers) if any(components.match_score(path, p) for p in pats)]
        if hit:
            free[hit[0]].append(path)
        else:
            missing.append(path)
    if missing:
        shown = ", ".join(missing[:5]) + (f" and {len(missing) - 5} more" if len(missing) > 5 else "")
        errors.append(f"V4: {len(missing)} source files belong to no component and are not listed as unassigned, for example {shown}.")
    for i, (u, _) in enumerate(covers):
        gaps.append({"kind": "coverage", "report": "components",
                     "statement": f"{len(free[i])} source file(s) in {u.get('paths', '')} belong to no component: {u.get('reason', '')}",
                     "how_to_confirm": "Check that these files really are not part of any component."})
    det = _entry(reports, "components.detail")
    if det and isinstance(det.get("entries"), list):
        have = {_name(e.get("component")) for e in det["entries"] if isinstance(e, dict)}
        want = {_name(r["name"]): r["name"] for r in rows}
        for key, name in want.items():
            if key not in have:
                errors.append(f"V4: the component {name} has no entry in Component details.")
        for e in det["entries"]:
            if isinstance(e, dict) and _name(e.get("component")) not in want:
                warnings.append(f"V4: Component details has an entry for {e.get('component')}, which is not in the Component catalog.")
    counts["v4"] = sum(1 for x in errors if x.startswith("V4"))
    return errors, warnings, gaps, counts


def validate(reports: dict, extract: dict, cites=None, facts=None, catalog=None) -> dict:
    """Run every check. {"errors", "warnings", "gaps", "counts", "unbacked"}."""
    result = {"errors": [], "warnings": [], "gaps": [], "counts": {}, "unbacked": {}}
    try:
        e, w, g, c = v5(reports, extract or {})
    except (AttributeError, TypeError, KeyError):
        e, w, g, c = [], [], [], {}  # a malformed card: V6 reports it
    result["errors"] += e
    result["warnings"] += w
    result["gaps"] += g
    result["counts"].update(c)
    tree = None
    try:
        tree = cites.tree()[0] if cites else None
    except Exception:  # noqa: BLE001 - a repository that cannot be listed: V4 then has nothing to check
        tree = None
    if tree:
        try:
            e, w, g, c = v4(reports, tree, facts)
            result["errors"] += e
            result["warnings"] += w
            result["gaps"] += g
            result["counts"].update(c)
        except (AttributeError, TypeError, KeyError):
            pass
    return result


def gap_extras(build, reports, extract, cites=None, facts=None, result=None) -> list:
    """The one list `cmd_render` and `cmd_confirm` both pass to `collect_gaps`: the build's coverage items, then the checks' items."""
    result = result if result is not None else validate(reports, extract, cites, facts)
    return process.coverage_items(build) + result["gaps"]
