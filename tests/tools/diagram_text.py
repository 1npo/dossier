#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright"]
# ///
"""Print, as JSON, the smallest rendered text height in each diagram of a dossier page at each width.

  uv run diagram_text.py PAGE.html [--widths 1500,400]

Output: [{"width", "report", "title", "min_height", "scrolls"}]. Used by the slow tests.
"""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

MIN_JS = """host => {
  let min = null;
  for (const el of host.querySelectorAll('svg *')) {
    const own = Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim());
    if (!own) continue;
    const h = el.getBoundingClientRect().height;
    if (h > 0 && (min === null || h < min)) min = h;
  }
  return min;
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--widths", default="1500,400")
    a = ap.parse_args()
    out = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in (int(w) for w in a.widths.split(",")):
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.goto(Path(a.html).resolve().as_uri())
            page.wait_for_timeout(300)
            for rid in page.eval_on_selector_all(".report", "els => els.map(e => e.id)"):
                page.evaluate("id => { location.hash = id; }", rid)
                page.wait_for_timeout(150)
                for i, host in enumerate(page.query_selector_all(f"#{rid} .mermaid-host"), 1):
                    page.wait_for_function("([r, i]) => document.querySelectorAll(`#${r} .mermaid-host`)[i - 1].dataset.done", arg=[rid, i], timeout=20000)
                    title = host.evaluate("h => (h.closest('.diagram').querySelector('h3') || {}).textContent || 'Diagram'")
                    out.append({"width": width, "report": rid, "title": title, "min_height": host.evaluate(MIN_JS),
                                "scrolls": host.evaluate("h => h.classList.contains('scrolls')")})
            page.close()
        browser.close()
    print(json.dumps(out))


if __name__ == "__main__":
    main()
