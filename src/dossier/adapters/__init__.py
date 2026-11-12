"""Turning one language's code into the standard outputs.

May import (besides itself and the standard library): resources, core, facts, tooling, findings.

  base      The adapter interface: the outputs an adapter may return, the context it runs in, and its base class.
  csharp    The C# adapter and its helpers.
  js        The JavaScript and TypeScript adapter and its helpers.
  python    The Python adapter and its helpers.
  registry  The adapters dossier ships, and which of them run for a repository's languages.
  repo      The repository-wide adapter: what belongs to no single language.
  tier_b    Tier B symbols: the top-level definitions of languages that have a tree-sitter grammar but no adapter.
"""

__all__ = ["base", "csharp", "js", "python", "registry", "repo", "tier_b"]
