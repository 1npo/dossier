import argparse
import json

import dossier
import migrate
import pytest
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
        errs, _ = schema.validate(rid, res["reports"][rid], sch, allow_pending=True, strict_notes=False)
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


# ------------------------------------------------------------------ the command


@pytest.fixture
def old_dossier(tmp_path, git_repo, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("DOSSIER_HOME", str(home))
    out = home / "repo"
    (out / "reports").mkdir(parents=True)
    for rid, rep in OLD.items():
        (out / "reports" / f"{rid}.json").write_text(json.dumps(rep))
    (out / "reports" / "data.json").write_text(json.dumps({"headline": "H", "summary": "- s", "blocks": []}))
    (out / "reports" / "gaps.json").write_text(json.dumps({"items": [{"report": "architecture", "kind": "unknown", "statement": "s"}]}))
    (out / "state.json").write_text(json.dumps({"skill_version": "0.4.0"}))
    return out, argparse.Namespace(repo=str(git_repo), dry_run=False)


def snapshot(out):
    return {n: (out / n).read_bytes() for n in ("state.json", "reports/overview.json")}


def test_migrate_command(old_dossier, capsys):
    out, args = old_dossier
    before = snapshot(out)
    dossier.cmd_migrate(args)
    summary = json.loads(capsys.readouterr().out)
    assert summary["cards_filled"] >= 4
    assert (out / "reports.legacy-v0.4.0" / "architecture.json").exists()
    assert not (out / "reports" / "architecture.json").exists()
    assert "cards" in json.loads((out / "reports" / "data.json").read_text())
    assert json.loads((out / "reports" / "gaps.json").read_text())["items"][0]["report"] == "components"
    assert snapshot(out) == before


def test_second_run_has_nothing_to_migrate(old_dossier, capsys):
    _, args = old_dossier
    dossier.cmd_migrate(args)
    capsys.readouterr()
    dossier.cmd_migrate(args)
    assert "Nothing to migrate." in capsys.readouterr().out


def test_dry_run_writes_nothing(old_dossier, capsys):
    out, args = old_dossier
    args.dry_run = True
    dossier.cmd_migrate(args)
    assert json.loads(capsys.readouterr().out)["cards_filled"] >= 4
    assert not (out / "reports.legacy-v0.4.0").exists() and (out / "reports" / "architecture.json").exists()


def test_existing_backup_stops_the_command(old_dossier):
    out, args = old_dossier
    (out / "reports.legacy-v0.4.0").mkdir()
    with pytest.raises(SystemExit):
        dossier.cmd_migrate(args)
    assert (out / "reports" / "architecture.json").exists()


def test_remap_gaps():
    g = migrate.remap_gaps({"items": [{"report": "failures"}, {"report": "risks"}]}, migrate.load_map()["retired"])
    assert [i["report"] for i in g["items"]] == ["behavior", "risks"]


def test_flow_notes_that_are_not_numbered_are_still_carried():
    blocks = card(result(), "interactions.flows")["blocks"]

    assert [b["type"] for b in blocks] == ["diagram", "text", "diagram", "text"]
