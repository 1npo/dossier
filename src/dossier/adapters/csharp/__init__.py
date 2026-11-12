"""The C# adapter and its helpers.

May import (besides itself and the standard library): what dossier.adapters may; never another language's subpackage.

  adapter    The C# adapter (frame): solutions, projects and the notes Gaps needs, plus the per-tool status for each step.
  api        What a C# project offers to other code (plan 011, D15): the per-file `public` flag and the real public API.
  entries    C# entry points that can be read from declarations and project files (plan 011, D9). Pure.
  graph      The C# graph: module items, type-use edges between files, and namespace cycles (plan 011, D8). Pure.
  models     Data entities and migrations for C#, from declarations and a little source text (plan 011, D13). Pure.
  project    C# solutions and projects, read from the text of the tracked files (plan 011, D7). Pure: no `dotnet`, no restore.
  queries    Tree-sitter queries for C#: declarations, usings, attributes and identifiers (plan 011, D14).
  scip       scip-dotnet for the C# adapter: install it from a hash-checked NuGet package (plan 011, D3).
  semgrep    Turns semgrep results for the C# rules into adapter items (plan 011, D9, D14). Pure.
  testsuite  C# tests, test configuration and static state, from declarations and project files (plan 011, D14). Pure.
"""

__all__ = ["adapter", "api", "entries", "graph", "models", "project", "queries", "scip", "semgrep", "testsuite"]
