"""The measured cards: drawn by code from extract/, never written by Claude.

May import (besides itself and the standard library): what dossier.render may, and render.markup; never render.page.

  blast    Blast radius (D5): what depends on a file, precomputed here and picked in the browser.
  cards    Bodies of the measured cards in reports 03 to 12: cards a script draws from `extract/` and the repository, not Claude (D8).
  change   Measured cards of report 10 (change and history), drawn from `extract/history.json` alone (D3).
  cs       What `reading.map` and `conventions.tooling` know about C# repositories (M5-23).
  env      The environment-variable and secret-signal cards of report `ops` (post-v1 items 17 and 18), drawn from the gatherer's facts.
  er       The `data.relationships` card, drawn from the extracted models (D9): every entity with every field, every relation.
  graph    The measured graph card (D8): `interactions.graph`.
  js       What `reading.map` and `conventions.tooling` know about JavaScript and TypeScript repositories (M4-20).
  people   Measured cards of report 13 (contributors) drawn from `extract/history.json` alone (D3, D4).
  tables   The tables of the two measured graph cards (D4): the component edge table and the module table.
  upgrade  Upgrade burden (D3): how far the runtime and the main frameworks are from end of life, from a shipped snapshot.
"""

__all__ = ["blast", "cards", "change", "cs", "env", "er", "graph", "js", "people", "tables", "upgrade"]
