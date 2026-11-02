"""Named ways to break a rendered dossier page, for tests of the checks that must notice.

  mutate(html, "conflict-css")

Each mutation takes the page text and returns the broken page text. Later tasks add more.
"""
from __future__ import annotations

import html as htmllib
import re

CONFLICT = (
    "<<<<<<< Updated upstream\n.dark { --tk-c: oklch(.8 .02 260);\n"
    "=======\n.dark { --tk-c: oklch(.82 .02 260);\n>>>>>>> Stashed changes\n"
)
SENTINEL_JS = 'document.documentElement.dataset.dossierJs = "ok";'


def conflict_css(html: str) -> str:
    """Three conflict lines in the stylesheet, between two rules, the way a failed autostash leaves them."""
    start = html.index("<style")
    end = html.index("</style>", start)
    at = html.index("}\n", start + int((end - start) * 0.4)) + 2
    return html[:at] + CONFLICT + html[at:]


def no_js_sentinel(html: str) -> str:
    if SENTINEL_JS not in html:
        raise ValueError("the page has no script sentinel to remove")
    return html.replace(SENTINEL_JS, "")


BIG_SEQUENCE = "sequenceDiagram\n" + "".join(f"    participant P{i} as Participant number {i}\n" for i in range(1, 10)) + "".join(
    f"    P{i}->>P{i + 1}: message from {i} to {i + 1}\n" for i in range(1, 9))
BIG_FLOW = "flowchart LR\n" + "".join(f"    N{i}[Component number {i}] --> N{i + 1}[Component number {i + 1}]\n" for i in range(1, 16))


def big_diagrams(html: str) -> str:
    """A 9-participant sequence diagram and a 16-node flowchart at the top of the first report."""
    def block(title, src):
        return (f'<div class="diagram flow"><div class="flow-bar"><h3>{title}</h3></div>'
                f'<div class="mermaid-host" data-src="{htmllib.escape(src, quote=True)}"></div></div>')
    first = re.search(r'<section class="report"[^>]*>', html)
    return html[:first.end()] + block("Injected sequence", BIG_SEQUENCE) + block("Injected flowchart", BIG_FLOW) + html[first.end():]


MUTATIONS = {"conflict-css": conflict_css, "no-js-sentinel": no_js_sentinel, "big-diagrams": big_diagrams}


def mutate(html: str, name: str) -> str:
    return MUTATIONS[name](html)
