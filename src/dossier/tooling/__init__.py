"""Running things on the host: which tools exist, the safe runner, the locked-worker clients, the .NET SDK check.

May import (besides itself and the standard library): resources, core, facts.

  dotnet_sdk    Which .NET SDK a repository asks for (global.json) and whether this machine has one (plan 011, D6).
  sandbox       The safe runner for restores and tools: empty environment plus an allowlist, scratch HOME, private caches, and a process-group timeout. This is hygiene, not isolation: the child still runs with the user's rights.
  shared_tools  Clients for the two locked workers (tree-sitter and semgrep) that every adapter shares.
  toolcheck     Which tools a repository needs, and which of them this machine has. Reads data/tools.json. Installs nothing.
"""

__all__ = ["dotnet_sdk", "sandbox", "shared_tools", "toolcheck"]
