"""Named ways to break a rendered dossier page, for tests of the checks that must notice.

  mutate(html, "conflict-css")

Each mutation takes the page text and returns the broken page text. Later tasks add more.
"""
from __future__ import annotations

import html as htmllib
import re

CONFLICT = (
    "<<<<<<< Updated upstream\n.dark { --tk-c: oklch(.8 .02 260);\n"
    "=======\n.dark { --tk-c: oklch(.82 .02 260);\n>>>>>>> Stashed changes\n"
)
SENTINEL_JS = 'document.documentElement.dataset.dossierJs = "ok";'


def conflict_css(html: str) -> str:
    """Three conflict lines in the stylesheet, between two rules, the way a failed autostash leaves them."""
    start = html.index("<style")
    end = html.index("</style>", start)
    at = html.index("}\n", start + int((end - start) * 0.4)) + 2
    return html[:at] + CONFLICT + html[at:]


def km_row_taller(html: str) -> str:
    """One CSS rule that report 02's knowledge map uses is changed."""
    at = html.index("</style>", html.index("<style"))
    return html[:at] + "\n.km-row { height: 40px }\n" + html[at:]


def no_js_sentinel(html: str) -> str:
    if SENTINEL_JS not in html:
        raise ValueError("the page has no script sentinel to remove")
    return html.replace(SENTINEL_JS, "")


BIG_SEQUENCE = "sequenceDiagram\n" + "".join(f"    participant P{i} as Participant number {i}\n" for i in range(1, 10)) + "".join(
    f"    P{i}->>P{i + 1}: message from {i} to {i + 1}\n" for i in range(1, 9))
BIG_FLOW = "flowchart LR\n" + "".join(f"    N{i}[Component number {i}] --> N{i + 1}[Component number {i + 1}]\n" for i in range(1, 16))


def big_diagrams(html: str) -> str:
    """A 9-participant sequence diagram and a 16-node flowchart at the top of the first report."""
    def block(title, src):
        return (f'<div class="diagram flow"><div class="flow-bar"><h3>{title}</h3></div>'
                f'<div class="mermaid-host" data-src="{htmllib.escape(src, quote=True)}"></div></div>')
    first = re.search(r'<section class="report"[^>]*>', html)
    return html[:first.end()] + block("Injected sequence", BIG_SEQUENCE) + block("Injected flowchart", BIG_FLOW) + html[first.end():]


PATHS = "<code>src/cannalerts/platforms/dutchie/client.py</code>, <code>src/cannalerts/platforms/dutchie/parser.py</code>"


def _table(tid: str, columns: int) -> str:
    head = "".join(f"<th>Column {i}</th>" for i in range(columns)) + '<th class="basis-cell">Basis</th><th class="src-cell">Source</th>'
    row = "".join(f"<td>{PATHS}</td>" for _ in range(columns)) + '<td class="basis-cell"><span class="badge">confirmed</span></td><td class="src-cell">[1] [2]</td>'
    return f'<div class="table-container"><table class="table" id="{tid}"><thead><tr>{head}</tr></thead><tbody><tr>{row}</tr></tbody></table></div>'


def wide_tables(html: str) -> str:
    """Two authored-style tables, 7 and 9 schema columns of long multi-path cells, in a card at the top of the first report."""
    card = ('<div class="card block llm" data-card="injected.tables"><header><h3>Injected tables</h3></header><section>'
            + _table("inj-7", 7) + _table("inj-9", 9) + "</section></div>")
    first = re.search(r'<section class="report"[^>]*>', html)
    return html[:first.end()] + card + html[first.end():]


def _drop_last_row(html: str, tbody_at: int = 0) -> str:
    starts = [m.start() for m in re.finditer(r"<tbody>", html)]
    end = html.index("</tbody>", starts[tbody_at])
    last = html.rindex("<tr>", starts[tbody_at], end)
    return html[:last] + html[end:]


def drop_row(html: str) -> str:
    """The last body row of the first table is not drawn."""
    return _drop_last_row(html)


def drop_column(html: str) -> str:
    """The second column of the first table is not drawn."""
    start = html.index("<thead>")
    end = html.index("</tbody>", start)
    part = html[start:end]
    part = re.sub(r"(<tr[^>]*>(?:<th[^>]*>.*?</th>))<th[^>]*>.*?</th>", r"\1", part, count=1, flags=re.S)
    part = re.sub(r"(<tr>(?:<td[^>]*>.*?</td>))<td[^>]*>.*?</td>", r"\1", part, flags=re.S)
    return html[:start] + part + html[end:]


def table_as_text(html: str) -> str:
    """The first table is flattened to text."""
    return re.sub(r"<table\b.*?</table>", "<p>a table that was flattened to text</p>", html, count=1, flags=re.S)


def entry_no_kv(html: str) -> str:
    """The first entry's key/value table is a definition list."""
    return re.sub(r'<table class="table kv".*?</table>', "<dl><dt>Purpose</dt><dd>text</dd></dl>", html, count=1, flags=re.S)


def drop_entry(html: str) -> str:
    return re.sub(r'<details class="entry".*?</details>', "", html, count=1, flags=re.S)


def drop_er_field(html: str) -> str:
    """The last row of the relationships field table is not drawn."""
    at = html.index('id="t-data-relationships-fields"')
    return html[:at] + _drop_last_row(html[at:])


def _first_card_body(html: str) -> int:
    """Where the first card's `<section>` opens its content (just after the tag)."""
    card = html.index('data-card="')
    return html.index("<section>", card) + len("<section>")


def wide_element(html: str) -> str:
    """A 2000 px wide block in the first card."""
    at = _first_card_body(html)
    return html[:at] + '<div style="width:2000px;height:20px;background:#ccc">a wide block</div>' + html[at:]


def icon_unsized(html: str) -> str:
    """An icon that draws at 300 px, as an icon with no size does."""
    at = _first_card_body(html)
    return html[:at] + '<svg viewBox="0 0 24 24" style="width:300px;height:300px"><circle cx="12" cy="12" r="10"/></svg>' + html[at:]


def tiny_diagram(html: str) -> str:
    """A flowchart of 60 nodes at the top of the first report."""
    source = "flowchart LR\n" + "".join(f"    N{i}[Node {i}] --> N{i + 1}[Node {i + 1}]\n" for i in range(60))
    return inject_diagrams(html, [("Injected big flowchart", source)])


def flow_no_notes(html: str) -> str:
    """The first set of notes under a flow diagram is not drawn (the class is renamed so nothing finds it)."""
    if 'class="diagram-notes"' not in html:
        raise ValueError("the page has no flow notes to remove")
    return html.replace('class="diagram-notes"', 'class="notes-gone" hidden', 1)


def overlap(html: str) -> str:
    """Two paragraphs, the second pulled up over the first."""
    at = _first_card_body(html)
    return html[:at] + '<p>The first paragraph of text in this card.</p><p style="margin-top:-1.4rem">The second paragraph, drawn over it.</p>' + html[at:]


def table_hidden(html: str, cards=()) -> str:
    """The first table of a card that has content and a table in its layout is not shown."""
    marks = [m for m in re.finditer(r'data-card="([^"]+)"', html)]
    for m, nxt in zip(marks, marks[1:] + [None]):
        segment = html[m.end():nxt.start() if nxt else len(html)]
        if m.group(1) in cards and '<table class="table"' in segment and "Not yet generated" not in segment:
            at = m.end() + segment.index('<table class="table"') + len('<table class="table"')
            return html[:at] + ' style="display:none"' + html[at:]
    raise ValueError("no card with content and a table was found")


def inject_diagrams(html: str, diagrams: list) -> str:
    """Diagrams [(title, mermaid source)] at the top of the first report."""
    first = re.search(r'<section class="report"[^>]*>', html)
    blocks = "".join(f'<div class="diagram flow"><div class="flow-bar"><h3>{htmllib.escape(t)}</h3></div>'
                     f'<div class="mermaid-host" data-src="{htmllib.escape(src, quote=True)}"></div></div>' for t, src in diagrams)
    return html[:first.end()] + blocks + html[first.end():]


def blast_data_removed(html: str) -> str:
    """The blast radius picker's data is gone."""
    out = re.sub(r'<script type="application/json" id="blast-data">.*?</script>', "", html, count=1, flags=re.S)
    if out == html:
        raise ValueError("the page has no blast-data")
    return out


def _table_span(html: str, tid: str):
    start = html.index(f'id="{tid}"')
    return start, html.index("</tbody>", start)


def hotspot_row_removed(html: str) -> str:
    """The last row of the hotspot file table is not drawn."""
    start, end = _table_span(html, "t-change-hotspots-files")
    return html[:html.rindex("<tr>", start, end)] + html[end:]


def chart_text_small(html: str) -> str:
    """The text in the hotspot scatter is 6 px."""
    start = html.index('<div class="chart-scroll">')
    end = html.index("</div>", start)
    return html[:start] + html[start:end].replace('font-size="12"', 'font-size="6"') + html[end:]


def workflow_table_to_text(html: str) -> str:
    """The team workflow table is replaced by a sentence."""
    start = html.index('id="t-contributors-workflow"')
    box = html.rindex('<div class="table-container', 0, start)
    end = html.index("</table></div>", start) + len("</table></div>")
    return html[:box] + "<p>The workflow is described here in words.</p>" + html[end:]


def owner_buttons_dead(html: str) -> str:
    """The Owner and Author buttons no longer answer a click."""
    out = html.replace("data-who-set=", "data-xx-set=")
    if out == html:
        raise ValueError("the page has no Owner and Author buttons")
    return out


MUTATIONS = {"km-row-taller": km_row_taller, "wide-element": wide_element, "icon-unsized": icon_unsized, "tiny-diagram": tiny_diagram, "flow-no-notes": flow_no_notes,
             "overlap": overlap, "table-hidden": table_hidden, "drop-row": drop_row, "drop-column": drop_column, "table-as-text": table_as_text, "entry-no-kv": entry_no_kv,
             "drop-entry": drop_entry, "drop-er-field": drop_er_field, "conflict-css": conflict_css, "no-js-sentinel": no_js_sentinel, "big-diagrams": big_diagrams, "wide-tables": wide_tables, "blast-data-removed": blast_data_removed, "hotspot-row-removed": hotspot_row_removed,
             "chart-text-small": chart_text_small, "workflow-table-to-text": workflow_table_to_text, "owner-buttons-dead": owner_buttons_dead}


def mutate(html: str, name: str, **kw) -> str:
    return MUTATIONS[name](html, **kw)
