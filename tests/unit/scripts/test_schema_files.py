import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent / "scripts"))
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
    assert sum(c["writer"] == "claude" for c in cards) == 42
    assert sum(c["writer"] == "script" for c in cards) == 23


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
    nums = [tuple(int(x) for x in q["id"].split(".")) for q in qs]
    assert nums == sorted(set(nums))
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
