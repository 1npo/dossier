"""The JavaScript and TypeScript adapter and its helpers.

May import (besides itself and the standard library): what dossier.adapters may; never another language's subpackage.

  adapter  The JavaScript and TypeScript adapter (frame): entry points from project files, and the per-tool status for each step.
  api      The real public API of a JavaScript package (plan 010, D17): what another package can import, as Node's rules say.
  entries  Entry points read from project files: package bins, scripts and main, Nx targets and Next.js file routes. Pure.
  prisma   A small parser for Prisma schema files (plan 010, D7). Pure: it takes the path and the text and runs nothing.
  project  JavaScript and TypeScript projects: which folders are installed and analysed as one unit. Pure, no file or process access.
  queries  Tree-sitter queries for JavaScript and TypeScript: tests, complexity and module-level state (plan 010, D8).
  reduce   Pure reducers from the JavaScript tools' JSON to adapter items (plan 010, D4, D12). Nothing here runs a process.
  semgrep  Turns semgrep results for the JavaScript rules into adapter items (plan 010, D6, D10). Pure.
  tools    Installing the JavaScript and TypeScript tools from one shipped lockfile, and the Node gate.
"""

__all__ = ["adapter", "api", "entries", "prisma", "project", "queries", "reduce", "semgrep", "tools"]
