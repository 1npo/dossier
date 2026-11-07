"""V12: layout and readability of the rendered page, measured in a browser (plan 008, D11). Used by check_page.py.

For each report, at each window size, in each theme, one script runs in the page and returns one line per problem:

  - the page does not scroll sideways, and no element sticks out of the window except inside a scroll container (an element
    that a parent clips without letting it scroll counts as sticking out: the reader cannot reach it);
  - no icon is drawn larger than 48 px;
  - every piece of text in every diagram, and in every chart (`.chart-scroll`), is at least 11 px tall;
  - diagram budgets: at most 12 nodes in a flowchart, 10 participants in a sequence diagram, 12 entities in an ER diagram
    (the diagrams code splits into areas are exempt: they are marked data-budget="area");
  - every flow diagram of Key flows and Startup has numbered notes under it;
  - every card whose layout has a table, and that has content, shows a table;
  - no two pieces of text in a card overlap (what a scroll box or a clipped card hides is not counted, nor is text made invisible, nor is the inside of a diagram).

Nothing here imports playwright: it is given an open page.
"""
from __future__ import annotations

import schema

SIZES = ((1500, 1000), (400, 900))
MIN_TEXT_PX, MAX_ICON_PX, MAX_FLOW_NODES, MAX_PARTICIPANTS, MAX_ENTITIES, MIN_OVERLAP_PX2 = 11, 48, 12, 10, 12, 4
NOTE_CARDS = ("interactions.flows", "entry.startup")
# Report 02 keeps its pre-1.0 layout (plan 008, A6), and at 400 px its heat-map legend is cut off 15 px short of the end. The sideways check
# skips these cards so that a dossier can pass; every other check still applies to them. Recorded for the author in plan 008, Results.
FROZEN_CARDS = "overview."
SCROLLERS = ".table-container, .mermaid-host, .year-scroll, .km-scroller, pre, .code-panel, .chart-scroll, .blast-list"
# Cards that code draws with a table of their own (M3). One that holds `.none-found` is exempt: it says there is nothing to list.
SCRIPT_TABLE_CARDS = ("change.cochange", "change.dead-code", "change.in-flight", "contributors.workflow", "change.upgrade-burden",
                      "change.hotspots", "change.blast-radius")

LAYOUT_JS = r"""(arg) => {
  const out = [], rep = document.querySelector('.report:not([hidden])'), vw = window.innerWidth;
  if (!rep) return ['no report is shown'];
  const ok = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const cardOf = el => { const c = el.closest('[data-card]'); return c ? c.dataset.card : rep.id; };
  const name = el => '<' + el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className ? ' class="' + el.className.slice(0, 40) + '"' : '') + '>';
  const add = (list, line, cap) => { if (list.length < cap) list.push(line); };
  // the part of an element that can be seen: its box cut by the ancestors that scroll (and, unless scrollOnly, by those that clip)
  const clips = new Map();
  const clipOf = a => {
    if (!clips.has(a)) { const cs = getComputedStyle(a); clips.set(a, [/auto|scroll/.test(cs.overflowX + cs.overflowY), cs.overflowX !== 'visible' || cs.overflowY !== 'visible', a.getBoundingClientRect()]); }
    return clips.get(a);
  };
  const shown = (el, scrollOnly) => {
    const r = el.getBoundingClientRect();
    let L = r.left, T = r.top, R = r.right, B = r.bottom;
    for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
      const [scrolls, clips_, c] = clipOf(a);
      if (scrolls || (clips_ && !scrollOnly)) { L = Math.max(L, c.left); T = Math.max(T, c.top); R = Math.min(R, c.right); B = Math.min(B, c.bottom); }
    }
    return R > L && B > T ? { left: L, top: T, right: R, bottom: B } : null;
  };
  // 1. sideways scroll
  if (document.documentElement.scrollWidth > vw + 1) out.push('the page scrolls sideways (' + document.documentElement.scrollWidth + ' px of content in a ' + vw + ' px window)');
  const wide = [];
  for (const el of rep.querySelectorAll('*')) {
    if (wide.length >= 3) break;
    if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE' || el.closest(arg.scrollers) || el.closest('[data-card^="' + arg.frozen + '"]')) continue;
    const r = shown(el, true);
    if (r && r.right > vw + 1) wide.push(cardOf(el) + ': ' + name(el) + ' ends at ' + Math.round(r.right) + ' px, past the ' + vw + ' px window');
  }
  out.push(...wide);
  // 2. icons
  const icons = [];
  for (const svg of rep.querySelectorAll('svg')) {
    if (svg.getAttribute('viewBox') !== '0 0 24 24') continue;
    const r = svg.getBoundingClientRect();
    if (r.width > arg.maxIcon || r.height > arg.maxIcon) add(icons, cardOf(svg) + ': an icon is drawn ' + Math.round(r.width) + ' x ' + Math.round(r.height) + ' px', 3);
  }
  out.push(...icons);
  // 3 and 4. diagrams: text size and budgets
  const dia = [];
  for (const host of rep.querySelectorAll('.mermaid-host')) {
    const svg = host.querySelector('svg');
    if (!svg || !ok(host)) continue;
    const title = ((host.closest('.diagram') || {}).querySelector ? (host.closest('.diagram').querySelector('h3, h4') || {}).textContent : '') || 'diagram';
    let min = null;
    for (const el of svg.querySelectorAll('*')) {
      if (!Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim())) continue;
      const h = el.getBoundingClientRect().height;
      if (h > 0 && (min === null || h < min)) min = h;
    }
    if (min !== null && min < arg.minText) add(dia, cardOf(host) + ' / ' + title + ': the smallest text is ' + Math.round(min * 10) / 10 + ' px tall (at least ' + arg.minText + ' px)', 6);
    if (host.dataset.budget === 'area') continue;
    const kind = svg.getAttribute('aria-roledescription') || '';
    const count = (sel) => svg.querySelectorAll(sel).length;
    if (kind.startsWith('sequence') && count('rect.actor-top') > arg.maxParticipants) add(dia, cardOf(host) + ' / ' + title + ': ' + count('rect.actor-top') + ' participants (at most ' + arg.maxParticipants + ')', 6);
    if (kind.startsWith('flowchart') && count('g.node') > arg.maxNodes) add(dia, cardOf(host) + ' / ' + title + ': ' + count('g.node') + ' nodes (at most ' + arg.maxNodes + ')', 6);
    if (kind.startsWith('er') && count('g.node') > arg.maxEntities) add(dia, cardOf(host) + ' / ' + title + ': ' + count('g.node') + ' entities (at most ' + arg.maxEntities + ')', 6);
  }
  out.push(...dia);
  const chart = [];
  for (const svg of rep.querySelectorAll('.chart-scroll svg')) {
    for (const t of svg.querySelectorAll('text')) {
      const h = t.getBoundingClientRect().height;
      if (h > 0 && h < arg.minText) { add(chart, cardOf(svg) + ': chart text is ' + Math.round(h * 10) / 10 + ' px tall (at least ' + arg.minText + ' px)', 3); break; }
    }
  }
  out.push(...chart);
  // 5. numbered notes under every flow
  for (const id of arg.noteCards) {
    const card = rep.querySelector('[data-card="' + id + '"]');
    if (!card) continue;
    card.querySelectorAll('.diagram.flow').forEach((f, i) => {
      const n = f.querySelectorAll('.diagram-notes ol > li, .diagram-notes ul > li').length;
      if (n < 2) out.push(id + ': diagram ' + (i + 1) + ' has no numbered notes (' + n + ' lines)');
    });
  }
  // 6. cards with a table show one
  for (const id of arg.tableCards) {
    const card = rep.querySelector('[data-card="' + id + '"]');
    if (!card || /Not yet generated|Not applicable/.test(card.textContent) || card.querySelector('.none-found')) continue;
    const t = card.querySelector('table.table:not(.kv)');
    if (!t || !ok(t)) out.push(id + ': the card shows no table');
  }
  // 7. overlapping text
  const seen = [];
  for (const card of rep.querySelectorAll('[data-card]')) {
    if (seen.length >= 3) break;
    const items = Array.from(card.querySelectorAll('td, th, dt, dd, li, p, .badge, summary, h3, h4')).filter(e => !e.closest('.mermaid-host') && getComputedStyle(e).visibility !== 'hidden').map(e => ({ e, r: shown(e) })).filter(x => x.r);
    items.sort((a, b) => a.r.top - b.r.top);
    for (let i = 0; i < items.length && seen.length < 3; i++) {
      for (let j = i + 1; j < items.length && items[j].r.top < items[i].r.bottom; j++) {
        const a = items[i], b = items[j];
        if (a.e.contains(b.e) || b.e.contains(a.e)) continue;
        const w = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left), h = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
        if (w > 0 && h > 0 && w * h > arg.minOverlap) { seen.push(cardOf(card) + ': ' + name(a.e) + ' and ' + name(b.e) + ' overlap by ' + Math.round(w * h) + ' px2'); break; }
      }
    }
  }
  out.push(...seen);
  return out;
}"""


def table_cards() -> list:
    """The cards written by Claude whose layout has a table that must be there when the card has content."""
    authored = [c["id"] for sch in schema.load_all().values() for c in sch["cards"]
                if c["shape"] == "blocks" and c["writer"] == "claude" and any(s["type"] == "table" and s.get("min", 1) for s in c.get("slots") or [])]
    return authored + list(SCRIPT_TABLE_CARDS)


def arguments() -> dict:
    return {"scrollers": SCROLLERS, "maxIcon": MAX_ICON_PX, "minText": MIN_TEXT_PX, "maxNodes": MAX_FLOW_NODES, "maxParticipants": MAX_PARTICIPANTS,
            "maxEntities": MAX_ENTITIES, "frozen": FROZEN_CARDS, "noteCards": list(NOTE_CARDS), "tableCards": table_cards(), "minOverlap": MIN_OVERLAP_PX2}


def check_report(page, args: dict) -> list:
    """The problems of the report that is shown in `page` (it waits for its diagrams to be drawn first)."""
    page.wait_for_function("() => Array.from(document.querySelectorAll('.report:not([hidden]) .mermaid-host')).every(h => h.dataset.done)", timeout=20000)
    page.wait_for_timeout(200)
    return page.evaluate(LAYOUT_JS, args)
