"""The adapter interface: the outputs an adapter may return, the context it runs in, and its base class.

An adapter turns one language's code into the standard outputs (entry points, import graph, symbols, ...).
This module imports no language adapter: the shipped ones are listed in `dossier.adapters.registry`, and the
extract stage that runs them is `dossier.pipeline.extract`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, ClassVar

from dossier.tooling import shared_tools

__all__ = ["ALWAYS_EXPECTED_SEG", "Adapter", "Context", "NO_EXTRACTORS", "OUTPUTS", "failure_reason"]

OUTPUTS = ("entry_points", "graph", "symbols", "io_candidates", "models", "tests", "dead", "blindspots")
ALWAYS_EXPECTED_SEG = {".venv", "venv", ".git", ".grimp_cache"}
NO_EXTRACTORS = "No extractors exist for these languages in this version of dossier."


@dataclass
class Context:
    checkout: Path
    sha: str
    tree: frozenset
    files: list
    area: Path
    restored: dict
    run: Callable
    treesitter: shared_tools.TreeSitter
    semgrep: shared_tools.Semgrep
    tool_versions: dict
    trusted: bool = True
    repo_name: str = "repo"
    tool_status: dict = field(default_factory=dict)
    details: dict = field(default_factory=dict)  # counts an adapter wants in the build log, nowhere else

    def read(self, path: str) -> str | None:
        """The text of a file in the checkout, or None when it cannot be read as UTF-8."""
        try:
            return (self.checkout / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    def tool_ok(self, tool: str) -> None:
        self.tool_status[tool] = {"status": "ok", "reason": None}

    def tool_skipped(self, tool: str, reason: str) -> None:
        self.tool_status[tool] = {"status": "skipped", "reason": reason}

    def tool_failed(self, tool: str, reason: str) -> None:
        self.tool_status[tool] = {"status": "failed", "reason": reason}


def failure_reason(e: BaseException) -> str:
    """The first line of an exception's message, or its type's name when the message is empty."""
    return (str(e).splitlines() or [type(e).__name__])[0]


class Adapter:
    name: ClassVar[str] = ""
    version: ClassVar[str] = "1"
    languages: ClassVar[tuple] = ()
    tools: ClassVar[tuple] = ()
    rules: ClassVar[tuple] = ()  # folders of semgrep rules; a change to any file in them makes an earlier build stale
    loads_repo_code: ClassVar[bool] = False
    expected_untracked: ClassVar[tuple] = ()
    blind_spots: ClassVar[tuple] = ()

    def extract(self, ctx: Context) -> dict[str, list[dict]]:
        """Return {output name: [items]} for any subset of OUTPUTS. Every item has 'path'."""
        raise NotImplementedError


ADAPTERS: tuple = ()  # kept for callers that pass their own tuple; the shipped adapters are registry.REGISTERED
