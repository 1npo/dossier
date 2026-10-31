#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright"]
# ///
"""Open a rendered dossier in a headless browser and check what only a browser can show.

  uv run check_page.py DOSSIER.html [--shots DIR]

Checks, in both the light and the dark theme:
  - every Mermaid diagram draws (no error banner, no console errors);
  - every piece of text inside a diagram has a contrast ratio of at least 4.5:1 against what is
    actually painted behind it (edge labels, node boxes, subgraph titles, sequence-diagram messages);
  - every table column header is sortable;
  - a citation tooltip appears at once on hover;
  - the code viewer: every highlight color has a contrast ratio of at least 4.5:1 on the panel and on a
    cited line; a click on a citation opens the panel with the cited lines marked, the keys and buttons
    (]  [  p  v  Esc, other sources, Go to reference) work, and citations of directories, commits and
    secret-looking files do not open it.

Exits 1 and prints one line per problem. With --shots it also saves a screenshot of each diagram,
which is worth opening: a script cannot judge layout, overlap or clipping.

First run needs a browser: `uv run --with playwright python -m playwright install chromium`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from viewer import TOKEN_CLASSES

from playwright.sync_api import sync_playwright

MIN_CONTRAST = 4.5

CONTRAST_JS = r"""
(host) => {
  const cv = document.createElement("canvas"); cv.width = cv.height = 1;
  const cx = cv.getContext("2d", { willReadFrequently: true });
  const rgba = (c) => {   // any CSS colour (rgb, oklch, color-mix...) to [r, g, b, a], by painting it
    cx.clearRect(0, 0, 1, 1); cx.fillStyle = "#000"; cx.fillStyle = c; cx.fillRect(0, 0, 1, 1);
    const d = cx.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2], d[3] / 255];
  };
  const lum = ([r, g, b]) => { const f = (x) => { x /= 255; return x <= .03928 ? x / 12.92 : Math.pow((x + .055) / 1.055, 2.4); }; return .2126 * f(r) + .7152 * f(g) + .0722 * f(b); };
  const over = (top, under) => { const a = top[3]; return [0, 1, 2].map(i => top[i] * a + under[i] * (1 - a)).concat([1]); };
  const SHAPES = new Set(["rect", "path", "polygon", "ellipse", "circle"]);
  const paint = (e) => {   // what this element paints as a background, or null
    const cs = getComputedStyle(e);
    if (SHAPES.has(e.localName)) {
      if (cs.fill === "none") return null;
      const c = rgba(cs.fill); c[3] *= parseFloat(cs.fillOpacity) * parseFloat(cs.opacity); return c[3] > 0.01 ? c : null;
    }
    const c = rgba(cs.backgroundColor); return c[3] > 0.01 ? c : null;
  };
  const page = rgba(getComputedStyle(host.closest(".card") || document.body).backgroundColor);
  const out = [];
  const texts = host.querySelectorAll("svg text, svg tspan, svg foreignObject span, svg foreignObject p, svg foreignObject div");
  const seen = new Set();
  for (const el of texts) {
    const own = Array.from(el.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent).join("").trim();
    if (!own) continue;
    if (el.localName === "tspan" && el.closest("text") && seen.has(el.closest("text"))) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || cs.display === "none") continue;
    // text must sit inside the box that clips it (a foreignObject), or it is invisible
    const fo = el.closest("foreignObject");
    let clipped = false;
    if (fo) {
      const rg = document.createRange(); rg.selectNodeContents(el); const tr = rg.getBoundingClientRect(), fr = fo.getBoundingClientRect();
      clipped = tr.width > 0 && (tr.bottom > fr.bottom + 1.5 || tr.top < fr.top - 1.5 || tr.right > fr.right + 1.5 || tr.left < fr.left - 1.5);
    }
    const fg = rgba(SHAPES.has(el.localName) || el.localName === "text" || el.localName === "tspan" ? cs.fill : cs.color);
    // What is painted behind the text, bottom to top: the page, SVG shapes whose box holds the text's
    // centre and that come earlier in the document, then the HTML ancestors inside a foreignObject.
    // (elementsFromPoint cannot be used: Mermaid labels are not hit-testable.)
    const cxp = r.left + r.width / 2, cyp = r.top + r.height / 2, svg = el.closest("svg");
    const layers = [];
    for (const sh of svg.querySelectorAll("rect, path, polygon, ellipse, circle")) {
      if (sh.closest("marker, defs") || !(sh.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING)) continue;
      const q = sh.getBoundingClientRect();
      if (q.width < 1 || q.height < 1 || cxp < q.left || cxp > q.right || cyp < q.top || cyp > q.bottom) continue;
      const pc = paint(sh); if (pc) layers.push(pc);
    }
    const html = [];
    for (let n = el; n && n.localName !== "foreignobject" && n.localName !== "svg"; n = n.parentElement) { const pc = paint(n); if (pc && n !== el) html.unshift(pc); else if (pc && n === el) html.unshift(pc); }
    let bg = page; for (const pc of layers.concat(html)) bg = over(pc, bg);
    const text = fg[3] < 1 ? over(fg, bg) : fg;
    const l1 = lum(text), l2 = lum(bg), ratio = (Math.max(l1, l2) + .05) / (Math.min(l1, l2) + .05);
    out.push({ clipped: clipped, text: own.slice(0, 40), ratio: Math.round(ratio * 100) / 100, fg: text.slice(0, 3).map(Math.round), bg: bg.slice(0, 3).map(Math.round) });
  }
  return out;
}
"""


SECRET_PATH = r"(^|/)(\.env(\.[^/]+)?|id_rsa|id_ed25519|[^/]+\.(pem|key|p12|pfx))$"

PANEL_JS = "() => { const p = document.getElementById('code-panel'); return !p.hidden && p.getBoundingClientRect().width > 0; }"
COUNT_JS = "() => document.getElementById('cp-count').textContent"
WIDTH_JS = """() => { const p = document.getElementById('code-panel'), s = document.createElement('span');
  s.style.cssText = 'position:absolute;visibility:hidden;width:90ch'; p.appendChild(s);
  const want = Math.min(s.getBoundingClientRect().width, innerWidth); s.remove(); return [p.getBoundingClientRect().width, want]; }"""
PIN_JS = "() => document.getElementById('cp-pin').getAttribute('aria-pressed') === 'true'"


TOKEN_JS = """(classes) => {
  const cv = document.createElement('canvas').getContext('2d', { willReadFrequently: true });
  const rgba = c => { cv.clearRect(0, 0, 1, 1); cv.fillStyle = '#000'; cv.fillStyle = c; cv.fillRect(0, 0, 1, 1); return Array.from(cv.getImageData(0, 0, 1, 1).data); };
  const lum = c => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }; return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2]); };
  const panel = document.getElementById('code-panel'), body = document.getElementById('cp-body'), out = [];
  const paper = rgba(getComputedStyle(panel).backgroundColor);
  for (const hit of [false, true]) {
    const row = document.createElement('div'); row.className = 'cl' + (hit ? ' hit' : ''); body.appendChild(row);
    let bg = paper;
    if (hit) { const h = rgba(getComputedStyle(row).backgroundColor); bg = paper.map((v, i) => i < 3 ? Math.round((h[i] * h[3] + v * (255 - h[3])) / 255) : 255); }
    for (const k of classes) {
      const el = document.createElement('i'); el.className = k; el.textContent = 'x'; row.appendChild(el);
      const fg = rgba(getComputedStyle(el).color), a = lum(fg), b = lum(bg);
      out.push({ cls: k, hit, ratio: Math.round((Math.max(a, b) + .05) / (Math.min(a, b) + .05) * 100) / 100 });
    }
    row.remove();
  }
  return out;
}"""


def check_tokens(page, scheme):
    """Every highlight color against the panel background, and against a cited line's."""
    return [f"[{scheme}] code viewer: token class '{r['cls']}' has contrast {r['ratio']}:1{' on a cited line' if r['hit'] else ''}"
            for r in page.evaluate(TOKEN_JS, list(TOKEN_CLASSES)) if r["ratio"] < MIN_CONTRAST]


def check_viewer(page, scheme, shots):
    """Drive the code viewer in the open page. Returns the problems it found."""
    out = []
    bad = lambda msg: out.append(f"[{scheme}] code viewer: {msg}")
    opened = lambda: page.evaluate(PANEL_JS)
    # pick a statement with several openable sources if there is one, else any openable citation
    pick = page.evaluate("""() => {
      const sups = Array.from(document.querySelectorAll('sup.cite')).filter(s => s.querySelector('a[data-view]'));
      const best = sups.find(s => s.querySelectorAll('a[data-view]').length > 1) || sups[0];
      return best ? { rid: best.closest('.report').id, n: sups.indexOf(best) } : null; }""")
    if not pick:
        return [f"[{scheme}] code viewer: no citation in the page can open it"]
    page.evaluate("id => { location.hash = id; }", pick["rid"])
    page.wait_for_timeout(150)
    sup_sel = f"#{pick['rid']} sup.cite:has(a[data-view])"
    sups = page.query_selector_all(sup_sel)
    sup = next((x for x in sups if len(x.query_selector_all("a[data-view]")) > 1), sups[0])
    a = sup.query_selector("a[data-view]")
    secret = page.evaluate("re => Array.from(document.querySelectorAll('[data-view]')).map(e => e.dataset.view).filter(p => new RegExp(re).test(p))", SECRET_PATH)
    if secret:
        bad(f"secret-looking files can be opened: {', '.join(sorted(set(secret)))}")

    a.scroll_into_view_if_needed()
    a.hover()
    if not page.evaluate("() => { const t = document.getElementById('cite-tip'); return !!t && !t.hidden && t.textContent.length > 0; }"):
        bad("the tooltip did not appear on hover")
    page.mouse.move(0, 0)
    a.click()
    if not opened():
        return out + [f"[{scheme}] code viewer: a click on a citation did not open the panel"]
    if not page.evaluate("() => document.querySelectorAll('#cp-body .cl.hit').length") and a.get_attribute("data-a"):
        bad("no line is marked as cited")
    out += check_tokens(page, scheme)
    got, want = page.evaluate(WIDTH_JS)
    if abs(got - want) > 1.5:
        bad(f"the panel is {got:.0f}px wide, expected {want:.0f}px (90 characters)")
    if shots:
        page.screenshot(path=str(Path(shots) / f"{scheme}-code-viewer.png"))

    n0 = page.evaluate(COUNT_JS)
    key = "]" if not page.evaluate("() => document.getElementById('cp-next').disabled") else "["
    page.keyboard.press(key)
    if page.evaluate(COUNT_JS) == n0:
        bad(f"pressing {key} did not change the counter ({n0})")
    other = page.query_selector("#cp-sources [data-src]:not([aria-current])")
    if other:
        before = page.evaluate(COUNT_JS)
        other.click()
        if page.evaluate(COUNT_JS) == before or not opened():
            bad("a click on another source of the statement did not open it")
    page.keyboard.press("p")
    if not page.evaluate(PIN_JS):
        bad("p did not pin the panel")
    page.keyboard.press("Escape")
    if not opened():
        bad("Esc collapsed a pinned panel")
    if not page.evaluate("() => parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--code-w-px')) > 0"):
        bad("a pinned panel did not make room for itself")
    page.keyboard.press("p")
    page.keyboard.press("Escape")
    if opened():
        bad("Esc did not collapse an unpinned panel")
    page.keyboard.press("v")
    if not opened():
        bad("v did not bring the panel back")
    page.keyboard.press("v")
    if opened():
        bad("v did not collapse the panel")
    page.keyboard.press("v")
    page.click("#cp-goto")
    page.wait_for_timeout(700)
    target = page.evaluate("""() => { const p = location.hash.slice(1), e = document.getElementById(p); if (!e) return null;
      const r = e.getBoundingClientRect(); return { id: p, top: Math.round(r.top), bottom: Math.round(r.bottom), visible: r.top >= 0 && r.bottom <= innerHeight, flash: e.classList.contains('flash') }; }""")
    if not target or not target["id"].startswith("ref-") or not target["visible"]:
        bad(f"Go to reference did not bring the reference list entry into view ({target})")
    if opened():
        bad("Go to reference left an unpinned panel open")

    # citations that must not open the viewer
    for label, tip_start in (("a directory", "directory "), ("a commit", "commit ")):
        els = page.query_selector_all(f"sup.cite a:not([data-view])[data-tip^='{tip_start}']")
        if els:
            els[0].evaluate("e => { location.hash = e.closest('.report').id; }")
            els[0].scroll_into_view_if_needed()
            els[0].click()
            if opened():
                bad(f"a click on {label} citation opened the panel")
    # a measured-facts marker explains itself in a popover and leaves the panel closed until its button is pressed
    els = page.query_selector_all("sup.cite a[data-fact]")
    if els:
        els[0].evaluate("e => { location.hash = e.closest('.report').id; }")
        els[0].scroll_into_view_if_needed()
        els[0].click()
        if opened():
            bad("a click on a measured facts citation opened the panel instead of the explanation")
        elif not page.is_visible(".fact-pop"):
            bad("a click on a measured facts citation showed no explanation")
        else:
            page.click(".fact-pop [data-open]")
            if not opened():
                bad("the gatherer code button in the explanation did not open the panel")
            page.keyboard.press("Escape")
    # a calendar cell shows its tooltip at once, with the lines added and deleted
    cell = page.query_selector(".report:not([hidden]) .zoom-lvl:not([hidden]) .cc.on[data-cal]")
    if cell:
        cell.scroll_into_view_if_needed()
        cell.hover()
        if not page.is_visible("#cite-tip .tp-r"):
            bad("a calendar cell showed no tooltip")
    return out


def check_knowledge(page, scheme):
    """Drive the contributor knowledge map: the tree draws, the controls and chips work, the tooltip shows, the minimap paints, and a phone-width page does not scroll sideways."""
    out = []
    if not page.query_selector("#km-root"):
        return out
    bad = lambda m: out.append(f"[{scheme}] knowledge map: {m}")
    page.evaluate("() => { location.hash = 'facts-contributors'; }")
    page.click('#km-vw [data-v="files"]')
    page.wait_for_timeout(200)
    rows = lambda: page.locator("#km-rows .km-row").count()
    if not rows():
        return out + [f"[{scheme}] knowledge map: the tree has no rows"]
    page.click('#km-zoom [data-v="1"]')
    top = rows()
    page.click('#km-zoom [data-v="99"]')
    if rows() <= top:
        bad("the All files zoom did not show more rows than Top level")
    page.click('#km-zoom [data-v="2"]')
    row = page.locator("#km-rows .km-row").first
    row.scroll_into_view_if_needed()
    row.hover()
    page.mouse.move(row.bounding_box()["x"] + 40, row.bounding_box()["y"] + 12)
    if not page.is_visible("#cite-tip .tp-h"):
        bad("a row showed no tooltip on hover")
    page.mouse.move(0, 0)
    page.locator(".km-chip").first.click()
    if page.inner_text("#km-th3").lower() != "their share":
        bad("focusing a contributor did not switch the third column to their share")
    page.locator(".km-chip").first.click()
    if page.evaluate("() => { const c = document.querySelector('#km-mini'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; for (let i = 3; i < d.length; i += 4) if (d[i]) return true; return false; }") is not True:
        bad("the minimap is blank")
    page.keyboard.press("Tab")
    if scheme == "light":
        page.set_viewport_size({"width": 400, "height": 900})
        page.wait_for_timeout(200)
        if not page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth"):
            bad("the page scrolls sideways at phone width")
        if page.is_visible(".km-thead > :nth-child(3)"):
            bad("the third column is still shown at phone width")
        page.set_viewport_size({"width": 1500, "height": 1000})
    return out


def check_theme(browser, path, scheme, shots):
    problems = []
    ctx = browser.new_context(color_scheme=scheme, viewport={"width": 1500, "height": 1000})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(Path(path).resolve().as_uri())
    page.wait_for_timeout(300)
    reports = page.eval_on_selector_all(".report", "els => els.map(e => e.id)")
    n_diagrams = 0
    for rid in reports:
        page.evaluate("id => { location.hash = id; }", rid)
        page.wait_for_timeout(150)
        hosts = page.query_selector_all(f"#{rid} .mermaid-host")
        for i, host in enumerate(hosts, 1):
            n_diagrams += 1
            page.wait_for_function("([r, i]) => document.querySelectorAll(`#${r} .mermaid-host`)[i - 1].dataset.done", arg=[rid, i], timeout=20000)
            title = host.evaluate("h => (h.closest('.diagram').querySelector('h3') || {}).textContent || 'Diagram'")
            if host.evaluate("h => h.classList.contains('failed')"):
                problems.append(f"[{scheme}] {rid} / {title}: the diagram did not draw")
                continue
            host.scroll_into_view_if_needed()
            for row in host.evaluate(CONTRAST_JS):
                if row["clipped"]:
                    problems.append(f"[{scheme}] {rid} / {title}: text '{row['text']}' is pushed outside its label box and is cut off")
                if row["ratio"] < MIN_CONTRAST:
                    problems.append(f"[{scheme}] {rid} / {title}: text '{row['text']}' has contrast {row['ratio']}:1 "
                                    f"(text rgb{tuple(row['fg'])} on rgb{tuple(row['bg'])})")
            if shots:
                host.screenshot(path=str(Path(shots) / f"{scheme}-{rid}-{i}.png"))
        # sortable tables
        for t in page.query_selector_all(f"#{rid} table.table:not([data-nosort])"):
            missing = t.evaluate("t => { const hr = t.tHead && t.tHead.rows[t.tHead.rows.length - 1]; return hr ? Array.from(hr.cells).filter(c => !c.querySelector('button')).map(c => c.textContent.trim()) : []; }")
            if missing and scheme == "light":
                problems.append(f"{rid} / table {t.get_attribute('id')}: columns not sortable: {', '.join(missing)}")
        # citation tooltip
        if scheme == "light":
            a = page.query_selector(f"#{rid} .cite a[data-tip]")
            g = page.query_selector(f"#{rid} .gid[data-tip]")
            if g:
                g.scroll_into_view_if_needed()
                g.hover()
                if not page.evaluate("() => { const t = document.getElementById('cite-tip'); return !!t && !t.hidden && t.classList.contains('note'); }"):
                    problems.append(f"{rid}: the gap ID tooltip did not appear on hover")
                page.mouse.move(0, 0)
            if a:
                a.scroll_into_view_if_needed()
                a.hover()
                shown = page.evaluate("() => { const t = document.getElementById('cite-tip'); return !!t && !t.hidden && t.textContent.length > 0; }")
                if not shown:
                    problems.append(f"{rid}: the citation tooltip did not appear on hover")
                page.mouse.move(0, 0)
    problems += check_viewer(page, scheme, shots)
    problems += check_knowledge(page, scheme)
    problems += [f"[{scheme}] browser error: {e}" for e in errors]
    ctx.close()
    return problems, n_diagrams


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--shots", help="directory for one screenshot per diagram and theme")
    a = ap.parse_args()
    if a.shots:
        Path(a.shots).mkdir(parents=True, exist_ok=True)
    problems = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for scheme in ("light", "dark"):
            got, n = check_theme(browser, a.html, scheme, a.shots)
            problems += got
        browser.close()
    print(json.dumps({"diagrams_checked": n, "problems": len(problems)}))
    for line in problems:
        print("FAIL", line)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
