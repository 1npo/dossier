#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright"]
# ///
"""Print, as JSON, whether the injected tables (ids starting `inj-`) of a page scroll sideways, at each width.

  uv run table_fit.py PAGE.html [--widths 1500,400]

Output: [{"width", "id", "scrollWidth", "clientWidth", "scrolls_class", "hint"}]. Used by the slow tests.
"""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

JS = """() => Array.from(document.querySelectorAll('.table-container')).filter(c => c.querySelector('table[id^=inj-]')).map(c => {
  const prev = c.previousElementSibling;
  return { id: c.querySelector('table').id, scrollWidth: c.scrollWidth, clientWidth: c.clientWidth,
           scrolls_class: c.classList.contains('scrolls'), hint: !!(prev && prev.classList.contains('table-hint')) };
})"""


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
            page.evaluate("() => { location.hash = document.querySelector('.report').id; }")
            page.wait_for_timeout(400)
            out += [{"width": width, **row} for row in page.evaluate(JS)]
            page.close()
        browser.close()
    print(json.dumps(out))


if __name__ == "__main__":
    main()
