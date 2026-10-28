"""Open items (inferences, unknowns, assumptions) with stable IDs, and the user's decisions about them.

Everything the user decides lives in state.json, which is never rebuilt from scratch. Items get an ID the first time
they are seen. On later builds an item keeps its ID when its wording changes a little, so a decision made once
keeps applying however often the dossier is rebuilt or the skill is updated.
"""
from __future__ import annotations

import difflib
import hashlib
import re

SCHEMA = 2
ACTIONS = ("confirm", "answer", "wrong")
MATCH = 0.8   # how similar two wordings must be to count as the same item


def norm(s):
    return " ".join(re.findall(r"[a-z0-9]+", re.sub(r"\[\[.*?\]\]", "", str(s).lower())))


def fp(s):
    return hashlib.sha1(norm(s).encode()).hexdigest()[:10]


def similarity(a, b):
    """1.0 or more when two wordings are very probably the same item, below 1.0 when not."""
    na, nb = norm(a), norm(b)
    ratio = difflib.SequenceMatcher(None, na, nb).ratio()
    wa, wb = set(na.split()), set(nb.split())
    jac = len(wa & wb) / max(1, len(wa | wb))
    la, lb = str(a).split(" · ")[0].strip().lower(), str(b).split(" · ")[0].strip().lower()
    same_label = " · " in str(a) and " · " in str(b) and la == lb and len(la) >= 4
    if ratio >= MATCH or jac >= 0.6 or (same_label and jac >= 0.25):
        return 1.0 + ratio
    return 0.0


def migrate(state):
    """Bring state.json from any earlier skill version up to date. Only ever adds."""
    state.setdefault("history", [])
    state.setdefault("corrections", [])
    state.setdefault("contributor_types", {})
    state.setdefault("tracked", [])
    state.setdefault("resolutions", {})
    state.setdefault("next_item", 1 + len(state["tracked"]))
    state["schema"] = SCHEMA
    return state


def sync(state, items):
    """Give every open item an ID (reusing the ID of the same item from earlier builds). Sets item['id']."""
    tracked = state["tracked"]
    by_fp = {t["fp"]: t for t in tracked}
    used = set()
    for it in items:
        f = fp(it["statement"])
        t = by_fp.get(f)
        if not (t and t["report"] == it["report"] and t["id"] not in used):
            t, best = None, 0.0
            for c in tracked:
                if c["id"] in used or c["report"] != it["report"]:
                    continue
                score = similarity(it["statement"], c["statement"])
                if score > best and score >= 1.0:
                    best, t = score, c
            if t is None:
                t = {"id": f"G{state['next_item']:03d}", "report": it["report"]}
                state["next_item"] += 1
                tracked.append(t)
        t.update(fp=f, statement=it["statement"], kind=it["kind"], confirm=it.get("confirm", ""), present=True)
        by_fp[f] = t
        used.add(t["id"])
        it["id"] = t["id"]
    for t in tracked:
        if t["id"] not in used:
            t["present"] = False
    return items


def apply(items, state):
    """Mark each item with its ID and the user's decision. A confirmed or answered claim becomes 'confirmed'."""
    res = state.get("resolutions", {})
    for it in items:
        node = it["node"]
        node["gid"] = it["id"]
        if node.get("conf") in ("inferred", "unknown"):
            node["was"] = node["conf"]
        r = res.get(it["id"])
        if r:
            node["user"] = r
            if r["action"] in ("confirm", "answer") and node.get("conf") in ("inferred", "unknown"):
                node["conf"] = "confirmed"
    return items


def find(state, key):
    key = key.strip().upper()
    for t in state["tracked"]:
        if t["id"] == key:
            return t
    return None
