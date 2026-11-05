"""Checks that compare the reports with the extractor output: V5 (every tool finding has a decision) and, later, V2, V3, V4, V7.

Each check returns `(errors, warnings, gap_items, counts)`. Gaps wording is fixed so item ids stay stable across builds.
"""
from __future__ import annotations

import builtins
import keyword
import re

import candidates
import checks_people
import checks_v3
import checks_v7
import components
import process
import render
import schema

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


ONE_ROW_CARDS = {"entry.catalog": ("entry_points", "entry point", "epg-"), "data.entities": ("models", "entity", "mdg-")}


def _word_in(name: str, text: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", text) is not None


def _same_entry_point(items: list) -> bool:
    """Several findings are one entry point when they are in the same file under the same name (found twice by two rules)."""
    return len({(it["path"], it.get("name") or "") for it in items}) == 1


def one_row_per_item(reports: dict, extract: dict, titles: dict) -> list:
    """D8: an entity or an entry point is decided on its own row, and a row lists every field of its entity."""
    errors, known, members = [], candidates.by_id(extract), candidates.group_members(extract)
    for rid, card, entry in _cards(reports):
        if card not in ONE_ROW_CARDS:
            continue
        output, noun, group_prefix = ONE_ROW_CARDS[card]
        title = titles.get(card, card)
        lists = [_as_list(node.get("cand")) for node in _nodes(entry)] + [_as_list(entry.get("cand"))] + [
            _as_list(d.get("cand")) for d in entry.get("dismissed") or [] if isinstance(d, dict)]
        for gid in sorted({i for ids in lists for i in ids if i.startswith(group_prefix) and i in members}):
            errors.append(f"V5: {title} decides the group {gid}; decide each {noun} on its own row: {', '.join(members[gid])}.")
        for block in entry.get("blocks") or []:
            if not isinstance(block, dict) or block.get("type") != "table":
                continue
            columns = [str(c) for c in block.get("columns") or []]
            for r in block.get("rows") or []:
                if not isinstance(r, dict):
                    continue
                items = [known[i] for i in _as_list(r.get("cand")) if i in known and not i.startswith(group_prefix)]
                names = [it.get("name") or it["path"] for it in items]
                if len(items) > 1 and not (card == "entry.catalog" and _same_entry_point(items)):
                    errors.append(f"V5: {title} puts {len(items)} {'entities' if card == 'data.entities' else 'entry points'} in one row ({', '.join(dict.fromkeys(names))}); give each its own row.")
                elif len(items) == 1 and card == "data.entities" and "Fields" in columns:
                    cells = r.get("cells") or []
                    text = str(cells[columns.index("Fields")]) if columns.index("Fields") < len(cells) else ""
                    left = [f["name"] for f in items[0].get("fields") or [] if f.get("name") and not _word_in(f["name"], text)]
                    if left:
                        errors.append(f"V5: {title}, {names[0]}: the Fields cell leaves out {', '.join(left)}.")
    return errors


def v5_env(reports: dict, facts: dict) -> list:
    """Every environment variable the gatherer found is named in a cell of the Inputs table."""
    entry = _entry(reports, "io.inputs")
    if not entry or "blocks" not in entry:  # missing, na or pending: V6 reports it
        return []
    text = " ".join(str(c) for node in _nodes(entry) for c in node.get("cells") or [])
    title = candidates.card_titles().get("io.inputs", "Inputs")
    out = []
    for var in (facts or {}).get("env_vars") or []:
        if not _word_in(var["name"], text):
            first = var.get("first") or {}
            where = f" (found in [[{first['path']}:{first['line']}]])" if first.get("path") and first.get("line") else ""
            out.append(f"V5: {title} does not list the environment variable {var['name']}{where}.")
    return out


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
    errors += one_row_per_item(reports, extract, titles)
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


SPAN = re.compile(r"`([^`]+)`")
NAME = re.compile(r"^[A-Za-z_][\w.]*(\(\))?$")
SKIP_WORDS = frozenset(keyword.kwlist) | frozenset(dir(builtins)) | {"true", "false", "null", "none"}


def _claim_text(c: dict) -> str:
    node = c.get("node") or {}
    return "\n".join([str(c.get("text") or "")] + [str(x) for x in node.get("cells") or []])


def _cited_text(cites, refs: list):
    """The cited lines of every file citation (the whole file when no lines are given), or None when no citation is a readable file.
    Directories and bad citations are skipped."""
    out = []
    for raw in refs:
        c = render.parse_cite(raw)
        if c["kind"] != "file":
            continue
        got = cites.repo.read(f"{cites.sha}:{c['path']}")
        if not got or got[0] != "blob":
            continue
        lines = got[1].decode("utf-8", "replace").splitlines()
        out.append("\n".join(lines[c["a"] - 1:c["b"]] if c["a"] else lines))
    return "\n".join(out) if out else None


def module_names(modules) -> frozenset:
    """Every dotted module name and each of its suffixes at a dot boundary (`a.b.c`, `b.c`, `c`)."""
    out = set()
    for m in modules or ():
        parts = str(m).split(".")
        out.update(".".join(parts[i:]) for i in range(len(parts)))
    return frozenset(out)


def _checked_span(span: str, files: set, modules=frozenset()) -> bool:
    """Is this backticked span a code identifier worth looking for? File names and module names are not."""
    s = span.strip()
    if not NAME.match(s) or s in files or s.casefold() in SKIP_WORDS or s.rstrip("()") in SKIP_WORDS:
        return False
    found = render.BARE_FILE.search(s)
    if (found and found.group(1) == s) or s in modules:
        return False
    return not (s.islower() and s.isalpha() and len(s) <= 3)


def _span_found(span: str, text: str) -> bool:
    s = span.strip()
    if s in text:
        return True
    if s.endswith("()") and s[:-2] in text:
        return True
    return "." in s and s.rstrip("()").rsplit(".", 1)[1] in text


def v2(reports: dict, cites, files: set, modules=()) -> tuple[list, list, list, dict]:
    """A name in backticks in a statement appears in the code the statement cites (D9). Warnings only.

    File names and module names (by their full dotted name or a suffix of it) are not looked for in the code.
    """
    warnings, gaps = [], []
    known = module_names(modules)
    for rid, rep in sorted(reports.items()):
        title = (schema.load(rid) or {}).get("title", rid)
        for c in render.claims_of(rid, rep or {}):
            refs = [x for x in c["cites"] if render.parse_cite(x)["kind"] == "file"]
            if not refs:
                continue
            text = _cited_text(cites, refs)
            if text is None:
                continue
            for span in dict.fromkeys(SPAN.findall(_claim_text(c))):
                if not _checked_span(span, files, known) or _span_found(span, text):
                    continue
                shown = " ".join(str(c["text"]).split())[:50]
                warnings.append(f"V2: {rid} '{shown}': {span} does not appear in the code it cites ({', '.join(refs)}).")
                gaps.append({"kind": "inference", "report": rid, "cite": refs,
                             "statement": f"A statement in {title} names `{span}`, which does not appear in the code it cites.",
                             "how_to_confirm": "Check the citation's line range, or the name."})
    return [], warnings, gaps, {"v2": len(warnings)}


def v2_recipes(reports: dict) -> tuple[list, list, int]:
    """A recipe's worked example cites a commit that did the same thing, unless it says it is unknown. Warnings only."""
    entry = _entry(reports, "conventions.recipes")
    if not entry:
        return [], [], 0
    title = candidates.card_titles().get("conventions.recipes", "Recipes")
    warnings, gaps = [], []
    for e in entry.get("entries") or []:
        if not isinstance(e, dict) or e.get("conf") not in ("confirmed", "inferred"):
            continue
        example = str((e.get("fields") or {}).get("worked_example") or "")
        cites = [c for c in e.get("cite") or [] if isinstance(c, str)] + render.inline_cites(example)
        if any(render.parse_cite(c)["kind"] == "commit" for c in cites):
            continue
        name = str(e.get("recipe") or "")
        warnings.append(f"V2: {title}, {name}: the worked example cites no commit.")
        gaps.append({"kind": "inference", "report": "conventions", "cite": [c for c in e.get("cite") or [] if isinstance(c, str)],
                     "statement": f"The recipe '{name}' has a worked example that cites no commit.",
                     "how_to_confirm": "Find the commit that did the same thing (git log -S) and cite it, or say it is unknown."})
    return warnings, gaps, len(warnings)


def validate(reports: dict, extract: dict, cites=None, facts=None, catalog=None) -> dict:
    """Run every check. {"errors", "warnings", "gaps", "counts", "unbacked"}."""
    result = {"errors": [], "warnings": [], "gaps": [], "counts": {}, "unbacked": {}, "info": []}
    try:
        e, w, g, c = v5(reports, extract or {})
    except (AttributeError, TypeError, KeyError):
        e, w, g, c = [], [], [], {}  # a malformed card: V6 reports it
    result["errors"] += e
    result["warnings"] += w
    result["gaps"] += g
    result["counts"].update(c)
    try:
        env_errors = v5_env(reports, facts or {})
    except (AttributeError, TypeError, KeyError):
        env_errors = []
    result["errors"] += env_errors
    result["counts"]["v5_env"] = len(env_errors)
    try:
        people_errors = checks_people.risk_source(reports)
    except (AttributeError, TypeError, KeyError):
        people_errors = []
    result["errors"] += people_errors
    result["counts"]["v5_people"] = len(people_errors)
    try:
        w, g, n = v2_recipes(reports)
        result["warnings"] += w
        result["gaps"] += g
        result["counts"]["v2_recipes"] = n
    except (AttributeError, TypeError, KeyError):
        pass  # a malformed card: V6 reports it
    tree = None
    try:
        tree = cites.tree()[0] if cites else None
    except Exception:  # noqa: BLE001 - a repository that cannot be listed: V4 then has nothing to check
        tree = None
    if cites:
        try:
            e, w, g, c = v2(reports, cites, set(tree or ()), {g["module"] for g in (extract or {}).get("graph", []) if g.get("kind") == "module"})
            result["warnings"] += w
            result["gaps"] += g
            result["counts"].update(c)
        except (AttributeError, TypeError, KeyError, OSError):
            pass
    if extract:
        try:
            _, w, g, c, unbacked = checks_v3.v3(reports, extract, components.catalog_rows(reports.get("components") or {}))
            result["warnings"] += w
            result["gaps"] += g
            result["counts"].update(c)
            result["unbacked"] = unbacked
        except (AttributeError, TypeError, KeyError):
            pass
        if not any(g.get("kind") == "module" for g in extract.get("graph", [])):
            result["info"].append("V3: no import graph was extracted, so diagram arrows were not checked.")
    if extract:
        _, w, g, c = checks_v7.v7(extract)
        result["gaps"] += g
        result["counts"].update(c)
    if extract and any(g.get("kind") == "module" for g in extract.get("graph", [])):
        result["gaps"].append({"kind": "coverage", "report": "change", "statement": "Stale feature flags and unused routes are not detected for Python.",
                               "how_to_confirm": "This is a known limit of this version of dossier."})
    if tree and extract:  # a dossier made before the extractors has no extract/: nothing to hold it to
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
