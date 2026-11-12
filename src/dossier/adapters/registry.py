"""The adapters dossier ships, and which of them run for a repository's languages.

The order of `REGISTERED` is the order of the adapter rows in the build log; it must not change without a reason.
"""
from __future__ import annotations

from dossier.adapters.base import Adapter
from dossier.adapters.csharp.adapter import CSharpAdapter
from dossier.adapters.js.adapter import JsAdapter
from dossier.adapters.python.adapter import PythonAdapter
from dossier.adapters.repo import RepoAdapter
from dossier.adapters.tier_b import TierBAdapter

REGISTERED: tuple[type[Adapter], ...] = (CSharpAdapter, JsAdapter, PythonAdapter, RepoAdapter, TierBAdapter)


def registered() -> tuple[type[Adapter], ...]:
    """The adapters dossier ships, in build-log order."""
    return REGISTERED


def detect(languages: list, adapters=None) -> list:
    adapters = registered() if adapters is None else adapters
    return [a() if isinstance(a, type) else a for a in adapters if "*" in a.languages or set(a.languages) & set(languages)]
