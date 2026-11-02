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


def test_added_row_gets_a_badge(make_cites):
    t = tbl()
    t["rows"][0]["added"] = True
    h = render.render_card(SCH["cards"][0], {"card": "x.tab", "blocks": [t]}, refs(make_cites), "x")
    assert "added by Claude" in h


def test_candidate_footer_counts_kept_dismissed_and_added(make_cites):
    t = tbl()
    t["rows"] = [dict(t["rows"][0], cand=["io-1", "io-2"]), dict(t["rows"][0], added=True)]
    entry = {"card": "x.tab", "blocks": [t], "dismissed": [{"cand": ["io-3"], "reason": "Not [[x]] needed."}]}
    h = render.render_card(SCH["cards"][0], entry, refs(make_cites), "x", {"fed": {"x.tab": 3}})
    assert "Tool findings: 3 found, 2 kept in 1 rows, 1 dismissed, 1 rows added by Claude." in h
    assert "<code>io-3</code>" in h and "Not [[x]] needed." in h


def test_candidate_footer_is_empty_when_nothing_was_fed(make_cites):
    h = render.render_card(SCH["cards"][0], {"card": "x.tab", "blocks": [tbl()]}, refs(make_cites), "x", {"fed": {}})
    assert "cand-foot" not in h


# ------------------------------------------------------------------ page wiring (M0-10)

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import report_section  # noqa: E402


def legacy_head(title, headline_html):
    return f'<header class="report-head"><h1>{title}</h1><p class="headline">{headline_html}</p>{render.SHADE_KEY}</header>'


def test_head_without_schema_is_the_legacy_string():
    assert render.head_html("capabilities", "Capabilities", "Hello") == legacy_head("Capabilities", "Hello")


def test_head_with_schema_adds_question_and_tier_key():
    sch = schema.load("entry")
    h = render.head_html("entry", "Entry points", "Hello", sch)
    assert sch["question"] in h and render.TIER_KEY in h and render.SHADE_KEY in h


def test_head_for_overview_differs_from_legacy_only_by_the_additions():
    h = render.head_html("overview", "This repository", "Hello", schema.load("overview"))
    assert report_section.normalize(h) == legacy_head("This repository", "Hello")


def test_with_contents_keeps_data_card_and_lists_title_only():
    html = render.schema_cards_html(schema.load("entry"), {}, None, "entry")
    body, toc = render.with_contents("entry", html)
    assert 'id="c-entry-catalog" data-card="entry.catalog"' in body
    assert '<a href="#c-entry-catalog">Entry points</a>' in toc and ">AEntry" not in toc and "<li><a href=\"#c-entry-startup\">Startup sequence</a>" in toc


def test_schema_cards_html_for_entry_order(make_cites):
    rep = {"cards": [{"card": "entry.catalog", "blocks": [{"type": "table", "columns": ["Kind", "Name", "Triggered by", "Starts at", "Notes"],
                                                            "rows": [{"cells": list("abcde"), "conf": "confirmed", "cite": ["a.py:1"]}]}]},
                     {"card": "entry.startup", "pending": True}]}
    h = render.schema_cards_html(schema.load("entry"), rep, refs(make_cites), "entry")
    assert re.findall(r' id="(c-[^"]+)"', h)[:2] == ["c-entry-catalog", "c-entry-startup"]


def test_existing_panel_titles_match_the_schema():
    import ast
    tree = ast.parse(Path(render.__file__).read_text())
    found = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "card":
            kw = {k.arg: k.value for k in n.keywords}
            if "cid" in kw and isinstance(n.args[0], ast.Constant):
                found.append((n.args[0].value, kw["cid"].value))
    assert {cid for _, cid in found} >= set(render.PANEL_ANCHORS)
    cards = render.schema_cards_by_id()
    for title, cid in found:
        assert cards[cid]["title"] == title, (title, cid)


def test_questions_links_point_at_real_ids(make_cites):
    ids = set(render.PANEL_ANCHORS.values()) | set(schema.REPORT_ORDER)
    for rid, sch in schema.load_all().items():
        ids |= {render.card_dom_id(c["id"]) for c in sch["cards"]}
    h = render.questions_body(refs(make_cites))
    hrefs = re.findall(r'href="#([^"]+)"', h)
    assert hrefs and all(x in ids for x in hrefs)
    assert "(report 03)" in h
