"""The page: citations and markup, measured cards, the process card, viewer, portfolio, summary.json.

May import (besides itself and the standard library): resources, core, facts, tooling, findings, history.

  markup         The page's HTML primitives: escaping, inline citations and Markdown, badges, tables and stat tiles.
  measured       The measured cards: drawn by code from extract/, never written by Claude.
  page           Validate report files and render the self-contained HTML dossier.
  portfolio      The portfolio page: one HTML file, `<home>/index.html`, that lists every dossier under the dossier home.
  process        The 'How this dossier was made' card, the records `render` adds to build.json, and the automatic Gaps items.
  summary        `summary.json`: the machine-readable summary written next to the page (spec section 9, plan 009 D10).
  summary_check  V8: a small validator for `summary.json`, covering exactly the JSON Schema keywords `src/dossier/data/schemas/summary.schema.json` uses.
  viewer         Choose which cited files to embed in the page for the code viewer, and how much of each.
"""

__all__ = ["markup", "measured", "page", "portfolio", "process", "summary", "summary_check", "viewer"]
