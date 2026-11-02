#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright"]
# ///
"""Print, as JSON, the V12 layout problems (scripts/check_layout.py) of a page at one width in one theme.

  uv run layout_probe.py PAGE.html [--width 1500] [--scheme light]

Output: a list of "report / problem" lines. Used by the slow tests, which need one answer fast.
"""
import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import check_layout  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--width", type=int, default=1500)
    ap.add_argument("--scheme", default="light")
    a = ap.parse_args()
    args, out = check_layout.arguments(), []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(color_scheme=a.scheme, viewport={"width": a.width, "height": 900}).new_page()
        page.goto(Path(a.html).resolve().as_uri())
        page.wait_for_timeout(300)
        for rid in page.eval_on_selector_all(".report", "els => els.map(e => e.id)"):
            page.evaluate("id => { location.hash = id; }", rid)
            page.wait_for_timeout(150)
            out += [f"{rid} / {line}" for line in check_layout.check_report(page, args)]
        browser.close()
    print(json.dumps(out))


if __name__ == "__main__":
    main()
