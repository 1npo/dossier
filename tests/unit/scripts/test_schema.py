import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent / "scripts"))
import schema  # noqa: E402


def card(i, **kw):
    base = {"id": f"x.{i}", "title": i.title(), "tier": "A", "priority": "P0", "writer": "claude"}
    base.update(kw)
    return base


TABLE = {"type": "table", "columns": ["A", "B"]}
SCH = {"report": "x", "title": "X", "question": "Q?", "cards": [
    card("tab", shape="blocks", slots=[TABLE], fixed={"on": "A", "values": ["one", "two"]}),
    card("flow", shape="flows", max_diagrams=2),
    card("ent", shape="entries", key="part", fields=[{"id": "f1", "label": "F1"}, {"id": "f2", "label": "F2"}]),
    card("comp", tier="M", shape="computed", writer="script"),
]}


def tbl(*rows, cols=("A", "B")):
    return {"type": "table", "columns": list(cols), "rows": [{"cells": list(r), "conf": "confirmed", "cite": ["a"]} for r in rows]}


def dia(): return {"type": "diagram", "mermaid": "flowchart LR\nA-->B"}
def txt(): return {"type": "text", "text": "1. Parse the arguments.\n2. Run the handler."}
def ent(): return {"part": "p", "fields": {"f1": "a", "f2": "b"}, "conf": "confirmed", "cite": ["a"]}


def good():
    return {"cards": [{"card": "x.tab", "blocks": [tbl(("one", "1"), ("two", "2"))]},
                      {"card": "x.flow", "blocks": [dia(), txt(), dia(), txt()]},
                      {"card": "x.ent", "entries": [ent()]}]}


def check(rep, key, **kw):
    errs, warns = schema.validate("x", rep, SCH, **kw)
    assert any("V6" in e and key in e for e in errs), (key, errs)


def test_passes_one_of_each_shape():
    assert schema.validate("x", good(), SCH) == ([], [])


def test_old_layout():
    check({"blocks": []}, "old layout")


def test_unknown_duplicate_order():
    r = good(); r["cards"].append({"card": "x.zzz", "pending": True}); check(r, "unknown card")
    r = good(); r["cards"].append(dict(r["cards"][0])); check(r, "more than once")
    r = good(); r["cards"].reverse(); check(r, "out of order")


def test_missing_required_and_script():
    r = good(); del r["cards"][2]; check(r, "missing")
    r = good(); r["cards"].append({"card": "x.comp", "blocks": []}); check(r, "script")


def test_columns_rows_blocks():
    r = good(); r["cards"][0]["blocks"] = [tbl(("a", "b"), cols=("A", "C"))]; check(r, "columns")
    r = good(); r["cards"][0]["blocks"] = [tbl()]; check(r, "no rows")
    r = good(); r["cards"][0]["blocks"].append(txt()); check(r, "unexpected block")


def test_na_and_pending():
    r = good(); r["cards"][0] = {"card": "x.tab", "na": "nothing here", "cite": ["a.py:1"]}
    assert schema.validate("x", r, SCH) == ([], [])
    r["cards"][0] = {"card": "x.tab", "na": "nothing here"}; check(r, "cite")
    r = good(); r["cards"][0] = {"card": "x.tab", "pending": True}
    assert schema.validate("x", r, SCH, allow_pending=True)[0] == []
    check(r, "pending")
    check(r, "pending", allow_pending=False)


def test_entry_fields():
    r = good(); r["cards"][2]["entries"][0]["fields"] = {"f1": "a"}; check(r, "fields")


def test_flows_start_with_diagram():
    r = good(); r["cards"][1]["blocks"] = [txt()]; check(r, "diagram")


def test_fixed_row_is_a_warning():
    r = good(); r["cards"][0]["blocks"] = [tbl(("`One`", "1"))]
    errs, warns = schema.validate("x", r, SCH)
    assert errs == [] and any("'two'" in w for w in warns)


def test_lint():
    assert schema.lint(SCH) == []
    bad = {"report": "x", "cards": [card("a", id="y.a", shape="computed"), card("b", tier="M", shape="blocks", slots=[TABLE])]}
    e = schema.lint(bad)
    assert any("must start" in x for x in e) and any("writer must be script" in x for x in e)


def test_load_all_skips_questions(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"report": "a"}))
    (tmp_path / "questions.json").write_text("[]")
    assert list(schema.load_all(tmp_path)) == ["a"]
    assert schema.load("questions", tmp_path) is None and schema.load_questions(tmp_path) == []


def test_card_entry_accepts_dismissed_and_unassigned_but_not_other_keys():
    r = good()
    r["cards"][0]["dismissed"] = [{"cand": ["io-1"], "reason": "Test helper."}]
    r["cards"][0]["unassigned"] = [{"paths": "docs/", "reason": "Docs."}]
    assert schema.validate("x", r, SCH) == ([], [])
    r["cards"][0]["bogus"] = 1
    check(r, "unknown keys")


class TestNowDrawnCards:
    def entry(self, **kw):
        return {"card": "data.relationships", **kw}

    def test_an_old_written_entry_is_a_warning_and_not_an_error(self):
        sch = schema.load("data")
        blocks = [{"type": "diagram", "title": "ER", "mermaid": "erDiagram\n A ||--o{ B : x", "conf": "confirmed", "cite": ["a.py:1"]}]

        errs, warns = schema.validate("data", {"cards": [self.entry(blocks=blocks)]}, sch, allow_pending=True)

        assert not [e for e in errs if "data.relationships" in e]
        assert any("drawn by code since 0.7.1" in w and "data.relationships" in w for w in warns)

    def test_a_script_card_that_was_always_drawn_still_rejects_a_written_entry(self):
        sch = schema.load("components")

        errs, _ = schema.validate("components", {"cards": [{"card": "components.map", "blocks": []}]}, sch, allow_pending=True)

        assert any("components.map" in e and "produced by a script" in e for e in errs)

    def test_relationships_is_a_script_card_with_no_slots(self):
        card = next(c for c in schema.load("data")["cards"] if c["id"] == "data.relationships")

        assert (card["writer"], card["shape"], "slots" in card) == ("script", "computed", False)


class TestFlowNotes:
    def errors(self, blocks):
        r = good()
        r["cards"][1]["blocks"] = blocks
        return schema.validate("x", r, SCH)[0]

    def test_a_diagram_followed_by_a_paragraph_needs_numbered_notes(self):
        errs = self.errors([dia(), {"type": "text", "text": "Onboarding tries discovery first."}])

        assert any("diagram 1 needs numbered notes after it" in e for e in errs)

    def test_a_diagram_with_nothing_after_it_needs_numbered_notes(self):
        errs = self.errors([dia(), txt(), dia()])

        assert any("diagram 2 needs numbered notes after it" in e for e in errs)

    def test_numbered_text_with_two_steps_passes(self):
        assert self.errors([dia(), txt()]) == []

    def test_numbers_may_be_followed_by_a_bracket(self):
        assert self.errors([dia(), {"type": "text", "text": "1) first\n2) second"}]) == []

    def test_a_list_block_with_two_items_passes(self):
        assert self.errors([dia(), {"type": "list", "items": ["first", "second"]}]) == []

    def test_a_list_block_with_one_item_is_not_enough(self):
        assert any("needs numbered notes" in e for e in self.errors([dia(), {"type": "list", "items": ["only one"]}]))

    def test_one_numbered_line_is_not_enough(self):
        assert any("needs numbered notes" in e for e in self.errors([dia(), {"type": "text", "text": "1. only one"}]))

    def test_numbered_lines_mixed_with_a_paragraph_are_not_numbered_notes(self):
        assert any("needs numbered notes" in e for e in self.errors([dia(), {"type": "text", "text": "1. first\n2. second\nAnd so on."}]))

    def test_migration_can_carry_unnumbered_notes(self):
        r = good()
        r["cards"][1]["blocks"] = [dia(), {"type": "text", "text": "Prose notes."}]

        assert schema.validate("x", r, SCH, strict_notes=False)[0] == []
