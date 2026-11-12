"""The prepare stages: work area, restore, the extract runner, incremental planning.

May import (besides itself and the standard library): resources, core, facts, tooling, findings, adapters, render.

  extract      The extract stage: run each detected adapter on the clean copy, filter its paths, and save extract/*.json.
  incremental  Work out which reports an update has to rewrite, so a rebuild does not re-read and re-write everything.
  restore      The restore stage: install a repository's locked dependencies into its working copy, if allowed.
  stages       The stages of `prepare` that run before the measuring: pin, tools, copy (checkout and restore) and extract.
  workarea     The per-repository working area: a verified clean checkout at the pinned commit, plus the trusted-ref check.
"""

__all__ = ["extract", "incremental", "restore", "stages", "workarea"]
