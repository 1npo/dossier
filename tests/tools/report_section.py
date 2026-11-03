"""Cut one report's section out of a rendered dossier page, digest it, or list card ids.

Used by the M0 check that report 02 is unchanged (docs/plans/005-m0-plan.md).
"""
import argparse
import hashlib
import json
import re
import sys

NORMALIZERS = (
    re.compile(r' data-card="[^"]*"'),
    re.compile(r'<div class="card-badges">.*?</div>', re.S),
    re.compile(r'<span class="badge tier [^"]*"[^>]*>.*?</span>', re.S),
    re.compile(r'<p class="question">.*?</p>', re.S),
    re.compile(r'<p class="tier-key">.*?</p>', re.S),
)


def section(html, rid):
    pat = r'<section class="report" id="%s" hidden>.*?</section>(?=<section class="report"|\s*<footer class="foot)' % re.escape(rid)
    m = re.search(pat, html, re.S)
    if not m:
        raise SystemExit(f"report section {rid!r} not found")
    return m.group(0)


def normalize(text):
    for rx in NORMALIZERS:
        text = rx.sub("", text)
    return text


def cards(html):
    out = {}
    for m in re.finditer(r'<section class="report" id="([^"]+)" hidden>(.*?)(?=<section class="report"|\s*<footer class="foot|$)', html, re.S):
        out[m.group(1)] = re.findall(r' data-card="([^"]*)"', m.group(2))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("rid", nargs="?")
    ap.add_argument("--digest", action="store_true")
    ap.add_argument("--normalize", action="store_true")
    ap.add_argument("--write")
    ap.add_argument("--cards", action="store_true")
    a = ap.parse_args(argv)
    html = open(a.html, encoding="utf-8").read()
    if a.cards:
        print(json.dumps(cards(html), indent=2))
        return
    if not a.rid:
        raise SystemExit("a report id is required")
    text = section(html, a.rid)
    if a.normalize:
        text = normalize(text)
    if a.write:
        open(a.write, "w", encoding="utf-8").write(text)
    if a.digest:
        print(hashlib.sha256(text.encode("utf-8")).hexdigest(), len(text))


if __name__ == "__main__":
    main()
