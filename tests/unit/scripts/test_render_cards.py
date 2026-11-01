import re

import render
import schema


def card(cid, tier="A", writer="claude", shape="blocks", **kw):
    return {"id": cid, "title": cid.split(".")[1].title(), "tier": tier, "priority": "P0", "writer": writer, "shape": shape, **kw}


def tbl(heading="Other heading"):
    return {"type": "table", "heading": heading, "columns": ["A", "B"],
            "rows": [{"cells": ["x", "y"], "conf": "confirmed", "cite": ["a.py:1"]}]}


def dia(title="D"):
    return {"type": "diagram", "title": title, "mermaid": "flowchart LR\nA-->B", "conf": "confirmed", "cite": ["a.py:1"]}


def refs(make_cites):
    cites = make_cites({"a.py": b"x\ny\n", "b.py": b"1\n"})
    cites.tree = lambda: (set(), set())  # the fake repo cannot list files
    return render.Refs("entry", cites)


SCH = {"report": "x", "cards": [
    card("x.tab", slots=[{"type": "table", "columns": ["A", "B"]}]),
    card("x.mea", tier="M", writer="script", shape="computed"),
    card("x.flow", tier="R", shape="flows"),
    card("x.ent", tier="R", shape="entries", key="component", fields=[{"id": "purpose", "label": "Purpose"}]),
]}


def test_placeholders_for_missing_pending_and_script(make_cites):
    r = refs(make_cites)
    for entry in (None, {"card": "x.tab", "pending": True}):
        assert "Not yet generated" in render.render_card(SCH["cards"][0], entry, r, "x")
    h = render.render_card(SCH["cards"][1], {"card": "x.mea", "pending": True}, r, "x")
    assert "Not yet generated" in h and "A tool fills this card in" in h


def test_na_shows_reason_and_marker(make_cites):
    h = render.render_card(SCH["cards"][0], {"card": "x.tab", "na": "no tables here", "cite": ["a.py:1"]}, refs(make_cites), "x")
    assert "Not applicable: no tables here" in h and "[1]" in h


def test_badge_outside_h3_and_shades(make_cites):
    r = refs(make_cites)
    a = render.render_card(SCH["cards"][0], None, r, "x")
    m = render.render_card(SCH["cards"][1], None, r, "x")
    assert "</h3><span class=\"badge tier" in a and 'data-card="x.tab"' in a
    assert "card block llm" in a and "card block fact" in m


def test_fixed_title_over_block_heading(make_cites):
    h = render.render_card(SCH["cards"][0], {"card": "x.tab", "blocks": [tbl("Something else")]}, refs(make_cites), "x")
    assert "<h3>Tab</h3>" in h and "Something else" not in h and "<table" in h


def test_flows_draw_both_diagrams_with_notes_after_first(make_cites):
    notes = {"type": "text", "text": "Walk through", "conf": "confirmed", "cite": ["b.py"]}
    h = render.render_card(SCH["cards"][2], {"card": "x.flow", "blocks": [dia("One"), notes, dia("Two")]}, refs(make_cites), "x")
    assert h.count('class="diagram flow"') == 2
    assert h.index("Walk through") < h.index("Two") and h.index("One") < h.index("Walk through")


def test_entries_collapsible_with_ids(make_cites):
    e = lambda n: {"component": n, "fields": {"purpose": f"does {n}"}, "conf": "confirmed", "cite": ["a.py:1"]}
    h = render.render_card(SCH["cards"][3], {"card": "x.ent", "entries": [e("one"), e("two")]}, refs(make_cites), "x")
    assert h.count('<details class="entry"') == 2
    assert 'id="c-x-ent-e1"' in h and 'id="c-x-ent-e2"' in h and h.index("e1") < h.index("e2")
    assert "<dt>Purpose</dt>" in h


def test_cards_in_schema_order(make_cites):
    h = render.schema_cards_html(SCH, {"cards": [{"card": "x.tab", "blocks": [tbl()]}]}, refs(make_cites), "x")
    assert re.findall(r'data-card="([^"]+)"', h) == ["x.tab", "x.mea", "x.flow", "x.ent"]


def test_bad_content_falls_back_to_placeholder(make_cites):
    h = render.render_card(SCH["cards"][0], {"card": "x.tab", "blocks": [{"type": "table"}]}, refs(make_cites), "x")
    assert "Not yet generated" in h
