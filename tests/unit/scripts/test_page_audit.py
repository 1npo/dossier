import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(SKILL / "tests" / "tools"))

import broken_pages  # noqa: E402
import buildlog  # noqa: E402
import page_audit  # noqa: E402
import render  # noqa: E402
import schema  # noqa: E402


def card_of(cid):
    return next(c for sch in schema.load_all().values() for c in sch["cards"] if c["id"] == cid)


def cites_for(make_cites):
    cites = make_cites({"a.py": b"x\ny\nz\n", "b.py": b"1\n"})
    cites.tree = lambda: (set(), set())
    return render.Refs("x", cites)


def row(*cells):
    return {"cells": list(cells), "conf": "confirmed", "cite": ["a.py:1"]}


def table_entry(rows=3):
    cols = card_of("components.cross-cutting")["slots"][0]["columns"]
    return {"card": "components.cross-cutting", "blocks": [{"type": "table", "columns": cols, "rows": [row(f"c{i}", f"how {i}", "a.py") for i in range(rows)]}]}


def entries_entry(n=2):
    card = card_of("components.detail")
    return {"card": "components.detail", "entries": [{card["key"]: f"Part {i}", "fields": {f["id"]: f"text {i}" for f in card["fields"]},
                                                       "conf": "confirmed", "cite": ["a.py:1"]} for i in range(n)]}


def flows_entry(notes=True):
    dia = {"type": "diagram", "title": "Run", "mermaid": "sequenceDiagram\nA->>B: x", "conf": "confirmed", "cite": ["a.py:1"]}
    text = {"type": "text", "text": "1. First step.\n2. Second step.", "conf": "confirmed", "cite": ["a.py:1"]}
    return {"card": "interactions.flows", "blocks": [dia, text, dia, text] if notes else [dia, {"type": "text", "text": "Prose.", "conf": "confirmed", "cite": ["a.py:1"]}]}


def page(make_cites, *entries, ctx=None):
    refs = cites_for(make_cites)
    return "".join(render.render_card(card_of(e["card"]), e, refs, e["card"].split(".")[0], ctx) for e in entries)


def reports_of(*entries):
    out = {}
    for e in entries:
        out.setdefault(e["card"].split(".")[0], {"cards": []})["cards"].append(e)
    return out


def audit(html, *entries, **kw):
    return page_audit.audit(html, reports_of(*entries), whole_page=False, **kw)


class TestAuditTables:
    def test_a_table_drawn_in_full_has_no_error(self, make_cites):
        e = table_entry()

        assert audit(page(make_cites, e), e) == []

    def test_a_missing_row_is_named_with_both_counts(self, make_cites):
        e = table_entry(3)

        errors = audit(broken_pages.mutate(page(make_cites, e), "drop-row"), e)

        assert errors == ["V11: components.cross-cutting: table 1 has 2 rows, expected 3."]

    def test_a_missing_column_is_named(self, make_cites):
        e = table_entry()

        errors = audit(broken_pages.mutate(page(make_cites, e), "drop-column"), e)

        assert any("components.cross-cutting: table 1 is missing the column 'Approach'" in x for x in errors)

    def test_a_table_flattened_to_text_is_reported(self, make_cites):
        e = table_entry()

        errors = audit(broken_pages.mutate(page(make_cites, e), "table-as-text"), e)

        assert errors == ["V11: components.cross-cutting: table 1 is not drawn: the card has no table."]


class TestAuditEntries:
    def test_entries_drawn_in_full_have_no_error(self, make_cites):
        e = entries_entry()

        assert audit(page(make_cites, e), e) == []

    def test_an_entry_without_its_key_value_table_is_reported(self, make_cites):
        e = entries_entry()

        errors = audit(broken_pages.mutate(page(make_cites, e), "entry-no-kv"), e)

        assert errors == ["V11: components.detail: entry 1 has no key/value table."]

    def test_a_missing_entry_is_reported(self, make_cites):
        e = entries_entry(2)

        errors = audit(broken_pages.mutate(page(make_cites, e), "drop-entry"), e)

        assert errors == ["V11: components.detail: 1 entries drawn, expected 2."]


class TestAuditFlows:
    def test_flows_with_numbered_notes_have_no_error(self, make_cites):
        e = flows_entry()

        assert audit(page(make_cites, e), e) == []

    def test_a_flow_whose_notes_are_prose_is_left_to_v6(self, make_cites):
        e = flows_entry(notes=False)

        assert audit(page(make_cites, e), e) == []

    def test_a_flow_whose_numbered_notes_were_not_drawn_is_reported(self, make_cites):
        e = flows_entry()
        html = page(make_cites, e).replace('<div class="diagram-notes">', '<div class="diagram-notes" hidden-notes="1"><p>x</p></div><div class="gone">', 1)

        assert audit(html, e) == ["V11: interactions.flows: diagram 1 has 0 numbered notes drawn, expected 2."]

    def test_a_list_block_as_notes_is_counted_by_its_items(self, make_cites):
        e = flows_entry()
        e["blocks"][1] = {"type": "list", "items": [{"text": "one", "conf": "confirmed", "cite": ["a.py:1"]}, {"text": "two", "conf": "confirmed", "cite": ["a.py:1"]},
                                                    {"text": "three", "conf": "confirmed", "cite": ["a.py:1"]}]}

        assert audit(page(make_cites, e), e) == []


class TestAuditNotApplicable:
    def test_a_not_applicable_card_shows_its_reason_and_citation(self, make_cites):
        e = {"card": "io.contracts", "na": "No contracts are declared.", "cite": ["a.py:1"]}

        assert audit(page(make_cites, e), e) == []

    def test_a_card_that_says_not_yet_generated_although_the_report_holds_it_is_reported(self, make_cites):
        e = table_entry()
        html = page(make_cites, e).replace("<table", "<p>Not yet generated.</p><table", 1)

        assert any("still says 'Not yet generated'" in x for x in audit(html, e))


ER_EXTRACT = {"models": [{"path": "db/schema.sql", "line": 1, "name": "runs", "kind": "sql-table", "fields": [
    {"name": "id", "type": "INTEGER", "line": 2, "ref": None, "pk": True}, {"name": "at", "type": "TEXT", "line": 3, "ref": None}]},
    {"path": "src/m.py", "line": 1, "name": "Run", "kind": "dataclass", "fields": [{"name": "id", "type": "int", "line": 2, "ref": None}]}],
    "graph": [{"kind": "import", "path": "a.py", "paths": ["b.py"], "from": "a", "to": "b", "lines": [1]}]}


class TestAuditDrawnCards:
    def html(self, make_cites):
        return page(make_cites, {"card": "data.relationships"}, ctx={"extract": ER_EXTRACT})

    def test_the_field_table_has_a_row_for_every_field(self, make_cites):
        assert page_audit.audit(self.html(make_cites), {}, ER_EXTRACT, whole_page=False) == []

    def test_a_field_missing_from_the_field_table_is_reported(self, make_cites):
        html = broken_pages.mutate(self.html(make_cites), "drop-er-field")

        errors = page_audit.audit(html, {}, ER_EXTRACT, whole_page=False)

        assert errors == ["V11: data.relationships: the table has 2 rows, expected 3."]

    def test_a_card_that_should_draw_a_table_but_does_not_is_reported(self, make_cites):
        html = '<div data-card="data.relationships"><p>nothing</p></div>'

        assert page_audit.audit(html, {}, ER_EXTRACT, whole_page=False) == [
            "V11: data.relationships: the table t-data-relationships-fields is not drawn."]


class TestAuditWholePage:
    def test_a_missing_card_is_reported(self):
        errors = page_audit.audit("<div data-card='dossier.about'></div>", {})

        assert "V11: the card dossier.process is not on the page." in errors

    def test_a_card_drawn_twice_is_reported(self):
        errors = page_audit.audit("<div data-card='dossier.about'></div><div data-card='dossier.about'></div>", {}, whole_page=False)

        assert errors == ["V11: the card dossier.about is on the page 2 times."]

    def test_the_process_and_question_tables_have_the_rows_their_sources_have(self):
        rows = "".join("<tr><td>x</td></tr>" for _ in range(len(buildlog.STEPS)))
        html = f'<div data-card="dossier.process"><table class="table" id="t-dossier-process"><thead><tr><th>No.</th></tr></thead><tbody>{rows}</tbody></table></div>'

        assert page_audit.audit(html, {}, whole_page=False, build={}) == []

    def test_a_process_table_with_a_missing_step_is_reported(self):
        rows = "".join("<tr><td>x</td></tr>" for _ in range(len(buildlog.STEPS) - 1))
        html = f'<div data-card="dossier.process"><table class="table" id="t-dossier-process"><thead><tr><th>No.</th></tr></thead><tbody>{rows}</tbody></table></div>'

        assert page_audit.audit(html, {}, whole_page=False, build={}) == [f"V11: dossier.process: the table has {len(buildlog.STEPS) - 1} rows, expected {len(buildlog.STEPS)}."]


    def test_a_dossier_without_a_build_record_has_no_process_table_to_check(self):
        html = '<div data-card="dossier.process"><p>Not yet generated.</p></div>'

        assert page_audit.audit(html, {}, whole_page=False) == []


class TestParse:
    def test_unclosed_and_void_tags_do_not_swallow_the_rest(self):
        root = page_audit.parse("<div id='a'><br><p>one<p>two</div><span id='b'></span>")

        assert [n.attrs["id"] for n in root.walk() if "id" in n.attrs] == ["a", "b"]

    def test_script_text_is_not_kept(self):
        root = page_audit.parse("<div><script>var x = 'Not yet generated';</script>ok</div>")

        assert root.text() == "ok"
