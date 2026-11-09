"""Build pages that hold what M6 adds, for the V11 and V12 tests (plan 012, M6-20 and M6-24).

  make_small(tmp) -> Path to the rendered page: the M3 page plus a catalog of 15 components, so the graph cards have views

The names are made up and the paths are real tracked files of the repository, so every citation resolves.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import m3_page  # noqa: E402

COMPONENTS = 15


def catalog(source: list, count: int = COMPONENTS) -> dict:
    """A `components` report whose catalog card names `count` components, each owning the files of one slice of `source`."""
    files = [p for p in source if p.endswith(".py")][:40]
    size = max(1, len(files) // count)
    rows = [{"cells": [f"Part{i:02d}", ", ".join(files[i * size:(i + 1) * size])]} for i in range(count) if files[i * size:(i + 1) * size]]
    return {"report": "components", "cards": [{"card": "components.catalog", "blocks": [{"type": "table", "headers": ["Component", "Paths"], "rows": rows}],
                                              "cite": ["facts:history"]}]}


def extend_small(out: Path, sha: str, source: list) -> None:
    (out / "reports" / "components.json").write_text(json.dumps(catalog(source)))


def make_small(tmp: Path) -> Path:
    return m3_page.make(tmp, extend=extend_small)


if __name__ == "__main__":
    import tempfile
    print(make_small(Path(tempfile.mkdtemp())))
