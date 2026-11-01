import render


def table(cols, rows):
    return {"type": "table", "columns": cols, "rows": [{"cells": r, "conf": "confirmed", "cite": ["a.py"]} for r in rows]}


CAT = ["Kind", "Name", "Triggered by", "Starts at", "Notes"]


def report(cards):
    return {"headline": "H", "summary": "- one", "cards": cards}


def run(make_cites, rep, monkeypatch, rid="entry"):
    cites = make_cites({"a.py": b"x\n"})
    return render.validate({rid: rep}, {}, cites, partial=True)


def test_valid_report_with_table_and_pending(make_cites, monkeypatch):
    rep = report([{"card": "entry.catalog", "blocks": [table(CAT, [["cli", "run", "user", "a.py", "n"]])]},
                  {"card": "entry.startup", "pending": True}])
    errs, _ = run(make_cites, rep, monkeypatch)
    assert errs == []


def test_wrong_columns(make_cites, monkeypatch):
    rep = report([{"card": "entry.catalog", "blocks": [table(["A", "B"], [["x", "y"]])]}])
    errs, _ = run(make_cites, rep, monkeypatch)
    assert any("V6" in e and "columns" in e for e in errs)


def test_wrong_row_width(make_cites, monkeypatch):
    rep = report([{"card": "entry.catalog", "blocks": [table(CAT, [["only", "two"]])]}])
    errs, _ = run(make_cites, rep, monkeypatch)
    assert any("row 1" in e for e in errs)


def test_old_layout(make_cites, monkeypatch):
    errs, _ = run(make_cites, {"headline": "H", "summary": "- one", "blocks": []}, monkeypatch)
    assert any("Run: dossier.py migrate" in e for e in errs)


def test_claims_rows_entries_na_and_pending():
    rep = {"cards": [
        {"card": "entry.catalog", "blocks": [table(CAT, [["a", "b", "c", "d", "e"], ["f", "g", "h", "i", "j"]])]},
        {"card": "components.detail", "entries": [{"component": "Core", "fields": {"purpose": "p", "how_it_works": "h"}, "conf": "confirmed", "cite": ["a.py"]}]},
        {"card": "entry.startup", "na": "no startup", "cite": ["a.py:1"]},
        {"card": "entry.other", "pending": True},
    ]}
    claims = render.claims_of("entry", rep)
    assert len(claims) == 4
    assert claims[2]["text"].startswith("Core") and claims[3]["conf"] == "confirmed" and claims[3]["cites"] == ["a.py:1"]


def test_overview_blocks_are_not_counted():
    assert render.claims_of("overview", {"blocks": [{"type": "text", "text": "x", "conf": "confirmed", "cite": ["a"]}]}) == []


def test_summary_text_accepts_string_and_list():
    assert render.summary_text({"summary": "- a\n- b"}) == "- a\n- b"
    assert render.summary_text({"summary": ["a", "b"]}) == "- a\n- b"
    assert render.summary_text({}) == ""
