#!/usr/bin/env python3
"""Print the card skeleton of rendered dossier pages and check that they are all the same (spec 11, item 2).

    python3 tests/tools/skeleton.py PAGE [PAGE...]

For each page: one line per card, in page order, `report  card id  title  tier`. Exit 1 unless every page has the same list, and then
say which cards differ. A card's presence depends on the schema alone, so a Python repository, a JavaScript repository and a mixed one
must all give the same skeleton.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

SECTION = re.compile(r'<section class="report" id="([^"]+)" hidden>(.*?)(?=<section class="report"|\s*<footer class="foot|$)', re.S)
CARD = re.compile(r'data-card="([^"]+)"><header><h3>(.*?)</h3>(.*?)</header>', re.S)
TIER = re.compile(r'class="badge tier [^"]*"[^>]*>([^<]*)<')


def skeleton(page: str) -> list:
    """[(report, card id, title, tier)] in page order."""
    out = []
    for rid, body in SECTION.findall(page):
        for cid, title, badges in CARD.findall(body):
            tier = TIER.search(badges)
            out.append((rid, cid, html.unescape(re.sub(r"<[^>]+>", "", title)), tier.group(1) if tier else ""))
    return out


def differences(a: list, b: list) -> list:
    """Lines saying how skeleton `b` differs from `a`."""
    lines = [f"missing: {c}" for c in a if c not in b] + [f"extra: {c}" for c in b if c not in a]
    if not lines and a != b:
        lines.append("same cards in a different order")
    return lines


def main(argv=None) -> int:
    paths = (argv if argv is not None else sys.argv[1:])
    if not paths:
        print(__doc__)
        return 2
    skeletons = [skeleton(Path(p).read_text(encoding="utf-8")) for p in paths]
    for p, s in zip(paths, skeletons):
        print(f"{p}: {len(s)} cards")
        for card in s:
            print("  " + "  ".join(card))
    bad = [(p, differences(skeletons[0], s)) for p, s in zip(paths[1:], skeletons[1:]) if s != skeletons[0]]
    for p, lines in bad:
        print(f"DIFFERENT {p}")
        print("\n".join("  " + x for x in lines))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
