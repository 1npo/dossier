#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright", "pillow"]
# ///
"""Compare how report 02 looks with a stored screenshot of how the pre-0.5 skill drew it (plan 008, D12).

  uv run golden02.py --write-baseline PAGE.html DIR     # screenshot the three cards into DIR (once, from the pre-M0 skill)
  uv run golden02.py PAGE.html DIR [--diff-dir OUT]     # compare the page with the baselines in DIR; exit 1 on a difference

The cards are #facts-git, #facts-contributors and #facts-dependencies at 1500 x 1000 px, in the light and the dark theme, after
hiding what the tier work added (tier badges, questions, the tier key: the same things report_section.normalize removes). A card
differs when its size changes or more than 0.5% of its pixels differ by more than 16 in any channel.
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

CARDS = ("facts-git", "facts-contributors", "facts-dependencies")
HIDE = ".badge.tier, .question, .tier-key { display: none !important; }"
MAX_DIFF_SHARE, CHANNEL_STEP = 0.005, 16


def shoot(page_path: str, out: Path) -> list:
    out.mkdir(parents=True, exist_ok=True)
    made = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for scheme in ("light", "dark"):
            page = browser.new_context(color_scheme=scheme, viewport={"width": 1500, "height": 1000}).new_page()
            page.goto(Path(page_path).resolve().as_uri())
            page.wait_for_timeout(500)
            page.evaluate("() => { location.hash = 'overview'; }")
            page.add_style_tag(content=HIDE)
            page.wait_for_timeout(1500)
            for card in CARDS:
                el = page.query_selector(f"#{card}")
                el.scroll_into_view_if_needed()
                page.wait_for_timeout(200)
                target = out / f"{card}-{scheme}.png"
                el.screenshot(path=str(target))
                made.append(target)
        browser.close()
    return made


def differs(baseline: Path, now: Path):
    """None when the two images match, else a sentence saying how they differ."""
    a, b = Image.open(baseline).convert("RGB"), Image.open(now).convert("RGB")
    if a.size != b.size:
        return f"the size changed from {a.size[0]} x {a.size[1]} to {b.size[0]} x {b.size[1]}"
    diff = ImageChops.difference(a, b)
    bad = sum(1 for px in diff.getdata() if max(px) > CHANNEL_STEP)
    share = bad / (a.size[0] * a.size[1])
    return f"{share:.2%} of the pixels differ (more than {MAX_DIFF_SHARE:.1%} is a change)" if share > MAX_DIFF_SHARE else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("dir")
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--diff-dir")
    a = ap.parse_args()
    if a.write_baseline:
        print("\n".join(str(p) for p in shoot(a.html, Path(a.dir))))
        return
    now = Path(a.diff_dir or (Path(a.dir) / ".now"))
    problems = []
    for shot in shoot(a.html, now):
        base = Path(a.dir) / shot.name
        if not base.exists():
            problems.append(f"{shot.name}: there is no baseline in {a.dir}")
            continue
        why = differs(base, shot)
        if why:
            problems.append(f"{shot.name}: {why}")
    for line in problems:
        print("FAIL", line)
    print(f"{len(CARDS) * 2} cards compared, {len(problems)} differ")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
