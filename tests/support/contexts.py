"""An adapter `Context` for unit tests, with harmless values for the fields a test does not care about."""
from pathlib import Path

from dossier.adapters import base

DEFAULTS = {"sha": "0" * 40, "tree": frozenset(), "files": [], "area": Path("area"), "restored": {}, "run": None,
            "treesitter": None, "semgrep": None, "tool_versions": {}}


def make_context(**fields) -> base.Context:
    """A real Context, so the adapters' calls to ctx.read and ctx.tool_* work as in a build."""
    return base.Context(**{**DEFAULTS, **fields})
