"""Named ways to break a rendered dossier page, for tests of the checks that must notice.

  mutate(html, "conflict-css")

Each mutation takes the page text and returns the broken page text. Later tasks add more.
"""
from __future__ import annotations

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


MUTATIONS = {"conflict-css": conflict_css, "no-js-sentinel": no_js_sentinel}


def mutate(html: str, name: str) -> str:
    return MUTATIONS[name](html)
