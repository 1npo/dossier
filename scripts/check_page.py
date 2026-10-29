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
  - a citation tooltip appears at once on hover.

Exits 1 and prints one line per problem. With --shots it also saves a screenshot of each diagram,
which is worth opening: a script cannot judge layout, overlap or clipping.

First run needs a browser: `uv run --with playwright python -m playwright install chromium`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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
        for t in page.query_selector_all(f"#{rid} table.table"):
            missing = t.evaluate("t => { const hr = t.tHead && t.tHead.rows[t.tHead.rows.length - 1]; return hr ? Array.from(hr.cells).filter(c => !c.querySelector('button')).map(c => c.textContent.trim()) : []; }")
            if missing and scheme == "light":
                problems.append(f"{rid} / table {t.get_attribute('id')}: columns not sortable: {', '.join(missing)}")
        # citation tooltip
        if scheme == "light":
            a = page.query_selector(f"#{rid} .cite a[data-tip]")
            if a:
                a.scroll_into_view_if_needed()
                a.hover()
                shown = page.evaluate("() => { const t = document.getElementById('cite-tip'); return !!t && !t.hidden && t.textContent.length > 0; }")
                if not shown:
                    problems.append(f"{rid}: the citation tooltip did not appear on hover")
                page.mouse.move(0, 0)
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
