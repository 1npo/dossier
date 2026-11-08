import re
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


class TestMeasuredCards:
    """V11 on the cards code draws from the history (M3): the right tables, columns and row counts, and `.none-found` for nothing."""

    TREE = {"src/a.py", "src/b.py", "src/c.py"}

    def ctx(self, **over):
        pair = lambda a, b, n: {"kind": "pair", "path": a, "a": a, "b": b, "co_commits": n, "commits_a": 5, "commits_b": 5, "share": 50}
        history = [{"kind": "meta", "path": ""}] + [
            {"kind": "file", "path": p, "lines": 10, "commits": 2, "commits_12m": 1, "last_changed": "2026-01-01"} for p in sorted(self.TREE)] + [
            pair("src/a.py", "src/b.py", 4), {"kind": "branch", "path": "", "ref": "origin/x", "sha": "a" * 40, "date": "2026-01-01", "ahead": 1, "behind": 0,
                                               "author": "Ann", "remote": True}] + [
            {"kind": "workflow", "path": "", "convention": c, "observed": "o", "evidence": "e", "commits": []} for c in ("a", "b", "c", "d", "e", "f")]
        graph = [{"kind": "module", "path": p, "module": p[:-3].replace("/", ".")} for p in sorted(self.TREE)]
        ctx = {"extract": {"history": history, "graph": graph, "dead": []}, "tree": set(self.TREE), "catalog": [{"name": "core", "paths": ["src/"]}],
               "facts": {}, "read": lambda p: None}
        ctx.update(over)
        return ctx

    def page(self, ctx):
        import measured

        class Refs:
            def mark(self, cites):
                return ""

        ids = ("change.hotspots", "change.cochange", "change.blast-radius", "change.dead-code", "change.in-flight", "contributors.workflow")
        return "".join(f'<div class="card" data-card="{cid}">{measured.body(cid, ctx, Refs())}</div>' for cid in ids)

    def errors(self, page, ctx):
        cards = {}
        for n in page_audit.parse(page).walk():
            if "data-card" in n.attrs:
                cards.setdefault(n.attrs["data-card"], []).append(n)
        return page_audit._check_measured(cards, ctx, page)

    def test_a_complete_page_has_no_error(self):
        ctx = self.ctx()

        assert self.errors(self.page(ctx), ctx) == []

    def test_a_missing_hotspot_row_is_an_error(self):
        ctx = self.ctx()

        errs = self.errors(broken_pages.hotspot_row_removed(self.page(ctx)), ctx)

        assert errs == ["V11: change.hotspots: table t-change-hotspots-files has 2 rows, expected 3."]

    def test_a_renamed_column_is_an_error(self):
        ctx = self.ctx()
        page = self.page(ctx).replace("<th>Co-commits</th>", "<th>Together</th>")

        assert any("t-change-cochange is missing the column 'Co-commits'" in e or "has the columns" in e for e in self.errors(page, ctx))

    def test_a_table_replaced_by_text_is_an_error(self):
        ctx = self.ctx()

        errs = self.errors(broken_pages.workflow_table_to_text(self.page(ctx)), ctx)

        assert errs == ["V11: contributors.workflow: the table t-contributors-workflow is not drawn."]

    def test_zero_rows_need_a_none_found_note_and_no_table(self):
        ctx = self.ctx()
        ctx["extract"]["history"] = [i for i in ctx["extract"]["history"] if i["kind"] != "branch"]
        page = self.page(ctx)

        assert self.errors(page, ctx) == []
        assert "none-found" in page
        assert any("does not say so" in e for e in self.errors(page.replace("none-found", "plain"), ctx))

    def test_blast_data_must_hold_every_file(self):
        ctx = self.ctx()
        page = self.page(ctx)

        assert self.errors(broken_pages.blast_data_removed(page), ctx) == ["V11: change.blast-radius: blast-data holds None files, expected 3."]

    def test_a_blast_table_row_missing_is_an_error(self):
        ctx = self.ctx()
        page = self.page(ctx)
        start = page.index('id="t-change-blast-radius"')
        end = page.index("</tbody>", start)
        page = page[:page.rindex("<tr", start, end)] + page[end:]

        assert any("t-change-blast-radius has 2 rows, expected 3" in e for e in self.errors(page, ctx))


class TestNotYetGenerated:
    def page(self, cid):
        return f'<div class="card" data-card="{cid}"><p class="muted"><strong>Not yet generated.</strong> A tool fills this card in.</p></div>'

    def test_a_change_card_that_says_so_is_an_error(self):
        errs = page_audit.audit(self.page("change.hotspots"), {}, whole_page=False)

        assert errs == ["V11: change.hotspots: the card still says 'Not yet generated'."]

    def test_other_reports_are_not_held_to_it(self):
        assert page_audit.audit(self.page("io.inputs"), {}, whole_page=False) == []

    def test_a_cut_card_is_accepted(self, monkeypatch):
        monkeypatch.setattr(render, "CUT_CARDS", ("change.hotspots",))

        assert page_audit.audit(self.page("change.hotspots"), {}, whole_page=False) == []


class TestOwnerTable:
    def build(self, history):
        import test_render

        t = test_render.TestContributorsOwnerButtons()
        return f'<div data-card="overview.contributors">{render.panel_contributors(t.facts(), t.Refs(), history)}</div>'

    def history(self, extra=()):
        import test_render

        return test_render.TestContributorsOwnerButtons().history() + list(extra)

    def errors(self, page, history):
        cards = {}
        for n in page_audit.parse(page).walk():
            if "data-card" in n.attrs:
                cards.setdefault(n.attrs["data-card"], []).append(n)
        return page_audit._check_measured(cards, {"extract": {"history": history}, "tree": {"a.py"}}, page)

    def test_the_owner_table_has_one_row_per_identity_that_owns_something(self):
        history = self.history()

        assert self.errors(self.build(history), history) == []

    def test_a_row_removed_from_the_owner_table_is_an_error(self):
        history = self.history([{"kind": "person", "path": "", "person": "bob@x.io", "name": "Bob", "type": "human", "commits": 2,
                                 "owned_commits": 2, "owned_lines": 5}])
        page = self.build(history)
        start = page.index('id="t-people-owner"')
        end = page.index("</tbody>", start)
        broken = page[:page.rindex("<tr>", start, end)] + page[end:]

        assert self.errors(broken, history) == ["V11: overview.contributors: table t-people-owner has 1 rows, expected 2."]


class TestAddedColumnNames:
    def entry(self, cid, rows=2):
        cols = card_of(cid)["slots"][0]["columns"]
        return {"card": cid, "blocks": [{"type": "table", "columns": cols, "rows": [row(*[f"v{i}"] * len(cols)) for i in range(rows)]}]}

    def test_decisions_table_with_a_source_column_passes(self, make_cites):
        e = self.entry("change.decisions")

        assert audit(page(make_cites, e), e) == []

    def test_ask_table_with_a_basis_column_passes(self, make_cites):
        e = self.entry("contributors.ask")

        assert audit(page(make_cites, e), e) == []

    def test_decisions_table_draws_source_then_basis_then_citations(self, make_cites):
        e = self.entry("change.decisions")

        html = page(make_cites, e)

        assert re.findall(r"<th[^>]*>([^<]*)</th>", html)[-3:] == ["Source", "Basis", "Citations"]


class TestReactTableAudit:
    GRAPH = [
        {"kind": "ui-component", "path": "src/Button.tsx", "line": 3, "name": "Button", "exported": True, "hooks": [], "provides": [], "consumes": []},
        {"kind": "ui-component", "path": "src/App.tsx", "line": 5, "name": "App", "exported": True, "hooks": ["useState"], "provides": [], "consumes": []},
        {"kind": "ui-component", "path": "src/App.tsx", "line": 20, "name": "Footer", "exported": False, "hooks": [], "provides": [], "consumes": []},
        {"kind": "renders", "path": "src/App.tsx", "paths": ["src/Button.tsx"], "from": "App", "to": "Button"},
    ]

    def check(self, drop_row=False):
        import measured

        class Refs:
            def mark(self, cites):
                return ""

        ctx = {"extract": {"graph": self.GRAPH}, "tree": set()}
        html = measured.body("interactions.graph", ctx, Refs())
        if drop_row:
            body = html[html.index("<tbody>", html.index('id="t-interactions-graph-react"')):]
            html = html.replace(re.search(r"<tr>.*?</tr>", body, re.S).group(0), "", 1)
        cards = {}
        for n in page_audit.parse(f'<div class="card" data-card="interactions.graph">{html}</div>').walk():
            if "data-card" in n.attrs:
                cards.setdefault(n.attrs["data-card"], []).append(n)
        return page_audit._check_measured(cards, ctx, html)

    def test_a_complete_table_has_no_error(self):
        assert self.check() == []

    def test_a_missing_row_is_an_error(self):
        assert self.check(drop_row=True) == ["V11: interactions.graph: table t-interactions-graph-react has 2 rows, expected 3."]


class TestPublicApiOnTheContractsCard:
    API = [{"kind": "public-api", "path": "src/a.ts", "line": 1, "name": n, "symbol_kind": "function", "package": "lib", "subpath": ".", "audience": "marked private"}
           for n in ("one", "two", "three")]
    CTX = {"extract": {"symbols": API, "graph": []}, "tree": set()}

    def card(self, make_cites, entry):
        return page(make_cites, entry, ctx=self.CTX)

    def na(self):
        return {"card": "io.contracts", "na": {"reason": "No contracts are offered.", "cite": ["a.py:1"]}}

    def authored(self):
        cols = card_of("io.contracts")["slots"][0]["columns"]
        return {"card": "io.contracts", "blocks": [{"type": "table", "columns": cols, "rows": [row("c", "offered", "web", "a.py", "none")]}]}

    def test_the_table_follows_the_authored_table(self, make_cites):
        html = self.card(make_cites, self.authored())

        assert html.index("Public API of each package") > html.index("Counterparty") and "t-io-contracts-api" in html

    def test_the_table_survives_a_not_applicable_entry(self, make_cites):
        assert "t-io-contracts-api" in self.card(make_cites, self.na())

    def test_a_pending_entry_has_no_table(self, make_cites):
        assert "t-io-contracts-api" not in self.card(make_cites, {"card": "io.contracts", "pending": True})

    def test_v11_passes_when_every_row_is_drawn(self, make_cites):
        e = self.authored()

        assert page_audit.audit(self.card(make_cites, e), reports_of(e), whole_page=False, measured=self.CTX) == []

    def test_v11_fails_when_a_row_is_missing(self, make_cites):
        e = self.authored()
        html = self.card(make_cites, e)
        start = html.index("<tbody>", html.index('id="t-io-contracts-api"'))
        html = html.replace(re.search(r"<tr>.*?</tr>", html[start:], re.S).group(0), "", 1)

        errs = page_audit.audit(html, reports_of(e), whole_page=False, measured=self.CTX)

        assert any("io.contracts" in x and "t-io-contracts-api" in x and "2 rows, expected 3" in x for x in errs)

    def test_a_repository_without_javascript_has_the_html_it_had_before(self, make_cites):
        e = self.authored()

        assert page(make_cites, e, ctx={"extract": {"symbols": [], "graph": []}}) == page(make_cites, e)
