"""Sampling for the independent claim check (`--verify`, D8). Pure: no I/O besides reading cited lines through `cites`."""
from __future__ import annotations
import hashlib
import random
import re

from dossier.render import markup
from dossier.render import page as render
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dossier.render.page import Cites

__all__ = ["check_results", "eligible", "keyed", "plain_text", "result_record", "sample", "sample_record"]

VERDICTS = ("supported", "not supported", "cannot tell")
SKIPPED_REPORTS = ("gaps",)


def base_key(c):
    """The claim's own id when it has one. Without one, a hash of its card and its citations, so rewording the claim keeps its
    verdict; a claim with no citation falls back to a hash of its text."""
    node = c.get("node") or {}
    label = node.get("id") or node.get("label")
    if label:
        return str(label)
    cites = sorted({str(x) for x in c.get("cites") or []})
    if cites:
        return "c:" + hashlib.sha1("\0".join([str(c.get("where") or ""), *cites]).encode()).hexdigest()
    return hashlib.sha1(str(c.get("text") or "").encode()).hexdigest()


def keyed(claims: list[dict]) -> list[dict]:
    """`claims` (one report's, in page order) with a unique `key` in each: the base key, and `#2`, `#3` for a repeat of it."""
    seen, out = {}, []  # type: dict, list
    for c in claims:
        k = base_key(c)
        seen[k] = seen.get(k, 0) + 1
        out.append({**c, "key": k if seen[k] == 1 else f"{k}#{seen[k]}"})
    return out


def claim_key(c):
    """The key `keyed` gave the claim, else its base key."""
    return c.get("key") or base_key(c)


def plain_text(text: str | None) -> str:
    """The claim as plain words: citation markers removed."""
    out = re.sub(r"\s*" + markup.INLINE_CITE.pattern, "", str(text or ""))
    return " ".join(out.split())


def line_cites(cites, c):
    """The claim's citations that resolve to a line range of a file at the pinned commit, as parsed citations."""
    found = []
    for raw in c.get("cites") or []:
        p = markup.parse_cite(raw)
        if p["kind"] != "file" or not p["a"]:
            continue
        st = cites.check(p)
        if not st["ok"] or st["type"] != "blob":
            continue
        lines, _ = cites.source(p["path"])
        if lines is None:
            continue
        found.append(p)
    return found


def eligible(reports: dict, cites: Cites) -> dict[str, list[dict]]:
    """{report id: [claim]} for the claims a checker can judge, sorted by (card, key)."""
    out = {}
    for rid, rep in reports.items():
        if rid in SKIPPED_REPORTS:
            continue
        good = [c for c in keyed(render.claims_of(rid, rep or {}))
                if c.get("conf") in ("confirmed", "inferred") and plain_text(c.get("text")) and line_cites(cites, c)]
        if good:
            out[rid] = sorted(good, key=lambda c: (str(c.get("where") or ""), claim_key(c)))
    return out


def excerpt(cites, cite):
    """The cited lines as `number: text`, taken from the pinned commit."""
    p = cite if isinstance(cite, dict) else markup.parse_cite(cite)
    lines, _ = cites.source(p["path"])
    lo, hi = p["a"], p["b"] or p["a"]
    return "\n".join(f"{n}: {lines[n - 1]}" for n in range(lo, min(hi, len(lines)) + 1))


def sample(elig: dict[str, list[dict]], seed: str, per_report: int, cites: Cites) -> list[dict]:
    """The items to check: up to `per_report` claims for each report, chosen from `seed`."""
    items: list = []
    for rid in sorted(elig):
        pool = elig[rid]
        for c in random.Random(f"{seed}:{rid}").sample(pool, min(per_report, len(pool))):
            items.append({
                "id": f"V{len(items) + 1:02d}",
                "report": rid,
                "card": str(c.get("where") or ""),
                "key": claim_key(c),
                "claim": plain_text(c["text"]),
                "code": [{"cite": p["key"], "text": excerpt(cites, p)} for p in line_cites(cites, c)],
            })
    return items


def check_results(sample_record: dict, results: list[dict]) -> list[str]:
    """Problems in an agent's answers against the recorded sample; an empty list means they can be recorded."""
    ids = [i["id"] for i in (sample_record.get("details") or {}).get("items", [])]
    problems, seen = [], set()
    if not isinstance(results, list):
        return ["The results must be a JSON array."]
    for r in results:
        rid = r.get("id") if isinstance(r, dict) else None
        if rid not in ids:
            problems.append(f"{rid}: not an id of the sample.")
            continue
        if rid in seen:
            problems.append(f"{rid}: answered more than once.")
        seen.add(rid)
        if r.get("verdict") not in VERDICTS:
            problems.append(f"{rid}: verdict {r.get('verdict')!r} is not one of {', '.join(VERDICTS)}.")
    problems += [f"{i}: no answer." for i in ids if i not in seen]
    return problems


def sample_record(seed: str, per_report: int, items: list[dict]) -> dict:
    """The build.json record that fixes which claims were sampled."""
    return {"step": "check", "part": "verify-sample", "by": "verify", "status": "ok",
            "details": {"seed": seed, "per_report": per_report,
                        "items": [{k: i[k] for k in ("id", "report", "card", "key")} for i in items]}}


def result_record(sample_record_: dict, results: list[dict]) -> dict:
    """The build.json record of the checker's verdicts, joined to the sampled claims."""
    by_id = {i["id"]: i for i in sample_record_["details"]["items"]}
    rows = [{"id": r["id"], "report": by_id[r["id"]]["report"], "key": by_id[r["id"]]["key"],
             "verdict": r["verdict"], "reason": str(r.get("reason") or "")} for r in results]
    n = lambda v: sum(1 for r in rows if r["verdict"] == v)  # noqa: E731
    return {"step": "check", "part": "verify", "by": "verify", "status": "ok",
            "counts": {"sampled": len(rows), "supported": n("supported"), "not_supported": n("not supported"), "cannot_tell": n("cannot tell")},
            "details": {"seed": sample_record_["details"]["seed"], "per_report": sample_record_["details"]["per_report"], "results": rows}}
