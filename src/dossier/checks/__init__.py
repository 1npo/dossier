"""V2 to V7 and V11 to V12, and --verify sampling.

May import (besides itself and the standard library): resources, core, facts, findings, render.

  browser     Open a rendered dossier in a headless browser and check what only a browser can show.
  layout      V12: layout and readability of the rendered page, measured in a browser (plan 008, D11). Used by check_page.py.
  page_audit  V11: the page draws every row, column and entry of its sources (plan 008, D10). Standard library only.
  people      V5 checks for reports 13 and 14 that look at who and what a card names, not at its layout.
  reports     Checks that compare the reports with the extractor output: V5 (every tool finding has a decision) and, later, V2, V3, V4, V7.
  v3          V3: every arrow in a flow diagram has an import or a call behind it (D9). Warnings only; unbacked arrows are listed as inferred.
  v7          V7: blind-spot hits are recorded in Gaps (D6). Never fails the build.
  verify      Sampling for the independent claim check (`--verify`, D8). Pure: no I/O besides reading cited lines through `cites`.
"""

__all__ = ["browser", "layout", "page_audit", "people", "reports", "v3", "v7", "verify"]
