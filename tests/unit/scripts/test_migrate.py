import migrate
import schema


def row(*cells, conf="inferred", cite=("a.py",), note="n"):
    return {"cells": list(cells), "conf": conf, "cite": list(cite), "note": note}


def dia(title, src="sequenceDiagram\nA->>B: hi"):
    return {"type": "diagram", "heading": title, "title": title, "mermaid": src, "conf": "confirmed", "cite": ["a.py"]}


def notes(on):
    return {"type": "text", "heading": f"Notes on {on}", "text": "walk", "conf": "confirmed", "cite": ["a.py"]}


OLD = {
    "code-tour": {"headline": "CT", "summary": "- ct", "blocks": [
        {"type": "table", "heading": "Reading order", "columns": ["Step", "Read", "What you learn", "Extra"],
         "rows": [row("1", "a.py", "everything", "x")]},
        dia("Path 1"), notes("path 1"), dia("Path 2"), notes("path 2"),
        {"type": "text", "heading": "Stray", "text": "t", "conf": "confirmed", "cite": ["a.py"]},
    ]},
    "architecture": {"headline": "AR", "summary": "- ar", "blocks": [
        {"type": "table", "heading": "Modules and components",
         "columns": ["Name", "Responsibility", "Key entry points", "Depends on", "Used by", "Approximate size"],
         "rows": [row("core", "does", "main", "none", "cli", "S")]},
    ]},
    "delivery": {"headline": "DE", "summary": "- de", "blocks": [
        {"type": "table", "heading": "Configuration", "columns": ["Setting", "Default", "How it is overridden"], "rows": [row("a", "b", "c")]},
        {"type": "table", "heading": "Secrets", "columns": ["Secret", "What it unlocks", "How it is supplied"], "rows": [row("a", "b", "c")]},
    ]},
    "overview": {"blocks": [
        {"type": "table", "heading": "Technology", "columns": ["What is used", "Area"], "rows": [row("python", "all")]},
    ]},
    "gaps": {"items": []},
}
SCHEMAS = schema.load_all()


def result(old=OLD):
    return migrate.convert(old, migrate.load_map(), SCHEMAS)


def card(res, cid):
    rid = cid.split(".")[0]
    return next(c for c in res["reports"][rid]["cards"] if c["card"] == cid)


def test_columns_reordered_and_missing_filled():
    t = card(result(), "reading.order")["blocks"][0]
    assert t["columns"] == ["Phase", "Step", "Read", "What you learn"]
    assert t["rows"][0]["cells"] == [migrate.MISSING_CELL, "1", "a.py", "everything"]
    assert t["rows"][0]["conf"] == "inferred" and t["rows"][0]["cite"] == ["a.py"] and t["rows"][0]["note"] == "n"
    assert "heading" not in t


def test_flows_get_diagrams_and_notes():
    blocks = card(result(), "interactions.flows")["blocks"]
    assert [b["type"] for b in blocks] == ["diagram", "text", "diagram", "text"]
    assert all("heading" not in b for b in blocks)


def test_config_secrets_needs_both_tables():
    assert "blocks" in card(result(), "ops.config-secrets")
    old = {**OLD, "delivery": {"blocks": OLD["delivery"]["blocks"][:1]}}
    res = result(old)
    assert card(res, "ops.config-secrets") == {"card": "ops.config-secrets", "pending": True}
    assert ("delivery", 0, "Configuration", "did not fit the card") in res["not_carried"]


def test_unused_blocks_listed_and_gaps_ignored():
    res = result()
    assert ("code-tour", 5, "Stray", "no card for this content") in res["not_carried"]
    assert not any(n[0] == "gaps" for n in res["not_carried"])
    assert ("overview", 0, "Technology", "reading.technologies") in res["carried"]


def test_every_claude_card_present_and_valid():
    res = result()
    for rid, sch in SCHEMAS.items():
        claude = [c["id"] for c in sch["cards"] if c["writer"] == "claude"]
        if not claude:
            assert rid not in res["reports"]
            continue
        assert [c["card"] for c in res["reports"][rid]["cards"]] == claude
        errs, _ = schema.validate(rid, res["reports"][rid], sch, allow_pending=True)
        assert errs == [], (rid, errs)


def test_headline_copied_only_when_filled():
    res = result()
    assert res["reports"]["reading"]["headline"] == "CT"
    assert res["reports"]["io"]["headline"] == migrate.NOT_YET


def test_shipped_map_is_consistent():
    m = migrate.load_map()
    cards = {c["id"]: c for sch in SCHEMAS.values() for c in sch["cards"]}
    reports = set(SCHEMAS)
    assert set(m["retired"].values()) <= reports and set(m["primary"]) <= reports
    for rule in m["rules"]:
        card = cards[rule["to"]]
        assert card["writer"] == "claude", rule
        if rule.get("type") == "table":
            assert list(rule["columns"]) in [s["columns"] for s in card["slots"] if s["type"] == "table"], rule
