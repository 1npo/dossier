import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent / "scripts"))
import render  # noqa: E402
import schema  # noqa: E402


def all_cards():
    return [c for sch in schema.load_all().values() for c in sch["cards"]]


def test_files_lint_clean():
    allsch = schema.load_all()
    assert set(allsch) == set(schema.REPORT_ORDER)
    for stem, sch in allsch.items():
        assert sch["report"] == stem
        assert isinstance(sch["question"], str) and sch["question"].strip()
        assert schema.lint(sch) == [], stem


def test_card_counts():
    cards = all_cards()
    assert len(cards) == 65
    assert sum(c["writer"] == "claude" for c in cards) == 41
    assert sum(c["writer"] == "script" for c in cards) == 24


def test_fixed_names_a_real_column_or_key():
    for c in all_cards():
        slots = [s for s in c.get("slots", []) if s["type"] == "table"]
        for fk, k in (("fixed", 0), ("fixed2", 1)):
            f = c.get(fk)
            if not f:
                continue
            if c["shape"] == "entries":
                assert f["on"] == c["key"], c["id"]
            else:
                assert f["on"] in slots[k]["columns"], c["id"]


def test_questions():
    ids = {c["id"]: c for c in all_cards()}
    qs = schema.load_questions()
    assert [q["id"] for q in qs] == [str(i) for i in range(1, len(qs) + 1)]
    named = set()
    for q in qs:
        assert q["question"].strip() and q["answers"]
        for a in q["answers"]:
            if isinstance(a, str):
                assert a in ids, a
                named.add(a)
            else:
                assert a["report"] in schema.REPORT_ORDER and a["label"]
    for cid, c in ids.items():
        assert c.get("informational") or cid in named, f"{cid} answers no question"


def test_report_list_matches_the_schema_order():
    assert [r for r, _, _ in render.REPORTS] == list(schema.REPORT_ORDER)
    for stem, sch in schema.load_all().items():
        assert sch["title"] == render.TITLES[stem]


def test_nav_groups_hold_every_report_once():
    ids = [r for _, group in render.NAV_GROUPS for r in group]
    assert sorted(ids) == sorted(schema.REPORT_ORDER)
    assert render.BARE_REPORTS == ("risks", "gaps", "corrections")


def test_card_counts():
    reports = {"entry": {"cards": [{"card": "entry.catalog", "blocks": []}, {"card": "entry.startup", "pending": True}]},
               "risks": {"cards": [{"card": "risks.tracker", "na": "x", "cite": ["a"]}]}}
    filled, pending = render.card_counts(reports)
    assert filled == 2 and filled + pending == 41
