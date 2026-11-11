"""Sampling for the independent claim check (`--verify`, D8). Pure: no I/O besides reading cited lines through `cites`."""
import hashlib
import random
import re

import render

VERDICTS = ("supported", "not supported", "cannot tell")
SKIPPED_REPORTS = ("gaps",)


def claim_key(c):
    """The claim's own id when it has one, else the SHA-1 of its text."""
    node = c.get("node") or {}
    label = node.get("id") or node.get("label")
    return str(label) if label else hashlib.sha1(str(c.get("text") or "").encode()).hexdigest()


def plain_text(text):
    """The claim as plain words: citation markers removed."""
    out = re.sub(r"\s*" + render.INLINE_CITE.pattern, "", str(text or ""))
    return " ".join(out.split())


def line_cites(cites, c):
    """The claim's citations that resolve to a line range of a file at the pinned commit, as parsed citations."""
    found = []
    for raw in c.get("cites") or []:
        p = render.parse_cite(raw)
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


def eligible(reports, cites):
    """{report id: [claim]} for the claims a checker can judge, sorted by (card, key)."""
    out = {}
    for rid, rep in reports.items():
        if rid in SKIPPED_REPORTS:
            continue
        good = [c for c in render.claims_of(rid, rep or {})
                if c.get("conf") in ("confirmed", "inferred") and plain_text(c.get("text")) and line_cites(cites, c)]
        if good:
            out[rid] = sorted(good, key=lambda c: (str(c.get("where") or ""), claim_key(c)))
    return out


def excerpt(cites, cite):
    """The cited lines as `number: text`, taken from the pinned commit."""
    p = cite if isinstance(cite, dict) else render.parse_cite(cite)
    lines, _ = cites.source(p["path"])
    lo, hi = p["a"], p["b"] or p["a"]
    return "\n".join(f"{n}: {lines[n - 1]}" for n in range(lo, min(hi, len(lines)) + 1))


def sample(elig, seed, per_report, cites):
    """The items to check: up to `per_report` claims for each report, chosen from `seed`."""
    items = []
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


def check_results(sample_record, results):
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


def sample_record(seed, per_report, items):
    """The build.json record that fixes which claims were sampled."""
    return {"step": "check", "part": "verify-sample", "by": "verify", "status": "ok",
            "details": {"seed": seed, "per_report": per_report,
                        "items": [{k: i[k] for k in ("id", "report", "card", "key")} for i in items]}}


def result_record(sample_record_, results):
    """The build.json record of the checker's verdicts, joined to the sampled claims."""
    by_id = {i["id"]: i for i in sample_record_["details"]["items"]}
    rows = [{"id": r["id"], "report": by_id[r["id"]]["report"], "key": by_id[r["id"]]["key"],
             "verdict": r["verdict"], "reason": str(r.get("reason") or "")} for r in results]
    n = lambda v: sum(1 for r in rows if r["verdict"] == v)  # noqa: E731
    return {"step": "check", "part": "verify", "by": "verify", "status": "ok",
            "counts": {"sampled": len(rows), "supported": n("supported"), "not_supported": n("not supported"), "cannot_tell": n("cannot tell")},
            "details": {"seed": sample_record_["details"]["seed"], "per_report": sample_record_["details"]["per_report"], "results": rows}}
