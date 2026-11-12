"""The component model, candidate findings with stable ids, people figures, open items and decisions.

May import (besides itself and the standard library): resources, core, facts.

  candidates          Candidate findings from the extractors: stable ids, groups and loading `extract/*.json`.
  candidates_history  The extra sections of `dossier candidates` for reports 10, 13 and 14: suggestions computed from `extract/history.json`.
  components          The component model (D4): suggestions for the components catalog, and the rules that decide which component owns a file.
  people              People figures from `extract/history.json`: display names, per-component ownership and the bus factor.
  resolve             Open items (inferences, unknowns, assumptions) with stable IDs, and the user's decisions about them.
"""

__all__ = ["candidates", "candidates_history", "components", "people", "resolve"]
