"""The whole git history folded once: per-file, per-pair, per-person figures, ownership, approvals, workflow.

May import (besides itself and the standard library): resources, core, facts, findings.

  github_owners  Pull request approvals, read with `gh` (D17). Optional: any failure leaves the commits unread and the caller falls back.
  ownership      Who owns a commit, a file and a line (D4).
  scan           Read the whole git history once and fold it into per-file, per-pair and per-person figures.
  workflow       The team workflow, measured from git alone: six fixed rows, plus the branches in flight.
"""

__all__ = ["github_owners", "ownership", "scan", "workflow"]
