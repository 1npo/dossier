#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright"]
# ///
"""Drive the interactive graph of one card in a browser and print what happened, as JSON (plan 012, M6-20).

  uv run graph_probe.py PAGE.html [--report components] [--card components.map]

Steps: open the report, wait for the root view, pick a view in the select, click an SVG node that has a view, press Up.
Output: {"views", "root", "picked", "clicked", "up", "caption", "nodes", "buttons"}.
"""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

STATE = """(card) => {
  const g = document.querySelector(`[data-card="${card}"] .igraph`);
  return { crumb: g.querySelector(".igraph-crumb").textContent, select: g.querySelector(".igraph-select").value,
           up: !g.querySelector(".igraph-up").hidden, caption: g.querySelector(".igraph-caption").textContent,
           nodes: g.querySelectorAll(".mermaid-host svg g.node").length, links: g.querySelectorAll(".mermaid-host svg g.node.igraph-link").length,
           buttons: g.querySelectorAll(".igraph-open [data-open]").length, failed: g.querySelector(".mermaid-host").classList.contains("failed") };
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--report", default="components")
    ap.add_argument("--card", default="components.map")
    a = ap.parse_args()
    out = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.goto(Path(a.html).resolve().as_uri() + "#" + a.report)
        sel = f'[data-card="{a.card}"] .igraph'
        page.wait_for_selector(sel + " .mermaid-host svg", timeout=20000)
        out["root"] = page.evaluate(STATE, a.card)
        views = page.eval_on_selector_all(sel + " .igraph-select option", "els => els.map(e => [e.value, e.textContent])")
        out["views"] = views
        target = views[1][0]
        page.select_option(sel + " .igraph-select", target)
        page.wait_for_function("([s, t]) => document.querySelector(s + ' .igraph-select').value === t && document.querySelector(s + ' .mermaid-host svg')", arg=[sel, target])
        page.wait_for_timeout(300)
        out["picked"] = page.evaluate(STATE, a.card)
        page.click(sel + " .igraph-up")
        page.wait_for_timeout(500)
        out["up"] = page.evaluate(STATE, a.card)
        link = sel + " .mermaid-host svg g.node.igraph-link"
        out["has_link"] = page.locator(link).count()
        if out["has_link"]:
            page.locator(link).first.click()
            page.wait_for_timeout(500)
            out["clicked"] = page.evaluate(STATE, a.card)
            page.click(sel + " .igraph-up")
            page.wait_for_timeout(500)
            out["back"] = page.evaluate(STATE, a.card)
        browser.close()
    print(json.dumps(out))


if __name__ == "__main__":
    main()
