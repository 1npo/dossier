"""Deterministic facts about the repository at the pin: files, languages, manifests, dependencies, environment reads, markers.

May import (besides itself and the standard library): resources, core.

  deps      Dependency analysis for the Dependencies card: which packages a repository declares, which of them its files import, and where. Everything is read from git objects at the pinned commit.
  env_scan  Environment-variable reads and credential-shaped strings, found by pattern matching on file text (post-v1 items 17 and 18).
  gather    Collect deterministic facts about a git repository at one pinned commit.
  markers   Findings for the change reports that a regex can make: decision markers, TODO counts, decision documents, long commit messages.
"""

__all__ = ["deps", "env_scan", "gather", "markers"]
