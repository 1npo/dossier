"""The Python adapter and its helpers.

May import (besides itself and the standard library): what dossier.adapters may; never another language's subpackage.

  adapter   The Python adapter: all eight outputs from grimp, vulture, scip-python, tree-sitter and semgrep.
  api       What a Python library offers to other packages: its public API (D10 of plan 012).
  depends   FastAPI `Depends(...)` and `Security(...)`: a `ref-edge` from the function that declares a dependency to the file that defines it.
  packages  What the Python adapter reads from project files: package roots, console scripts, import rules, test settings.
  project   Which folders of a repository are Python projects, and which tracked `.py` files belong to each.
  queries   Tree-sitter queries for Python: models, tests, module-level state and imports.
  scip      Installing and running scip-python from a committed lockfile.
  tools     Clients for the locked Python worker (grimp and vulture), in the style of `shared_tools`.
"""

__all__ = ["adapter", "api", "depends", "packages", "project", "queries", "scip", "tools"]
