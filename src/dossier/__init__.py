"""The dossier skill's Python package: it measures a repository, renders the dossier page and checks it.

Subpackages, lowest first (each may import only the ones before it; see docs/developer-guide.md#architecture):

  resources   Where the package finds its files: the data shipped inside it and the skill folder around it.
  core        Leaf utilities with no domain knowledge: config file, build log, graph helpers, card schema loader, SCIP reader.
  facts       Deterministic facts about the repository at the pin: files, languages, manifests, dependencies, environment reads, markers.
  tooling     Running things on the host: which tools exist, the safe runner, the locked-worker clients, the .NET SDK check.
  findings    The component model, candidate findings with stable ids, people figures, open items and decisions.
  history     The whole git history folded once: per-file, per-pair, per-person figures, ownership, approvals, workflow.
  adapters    Turning one language's code into the standard outputs.
  render      The page: citations and markup, measured cards, the process card, viewer, portfolio, summary.json.
  checks      V2 to V7 and V11 to V12, and --verify sampling.
  pipeline    The prepare stages: work area, restore, the extract runner, incremental planning.
  cli         Argument parsing and one module per group of commands; `main()` is what the launcher runs.

`data/` holds the package data, read only through `dossier.resources`. `__main__` runs the CLI (`python -m dossier`).
"""

__all__ = ["resources", "core", "facts", "tooling", "findings", "history", "adapters", "render", "checks", "pipeline", "cli"]
