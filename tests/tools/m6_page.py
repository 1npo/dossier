"""Build pages that hold what M6 adds, for the V11 and V12 tests (plan 012, M6-20 and M6-24).

  make_small(tmp) -> Path to the rendered page: the M3 page plus a catalog of 15 components, so the graph cards have views
  make(tmp)       -> Path to the large page (D14): 60 components over 15 areas, 400 modules with 1,200 imports (group nodes and the
                     edge filter), a Shell and a Rust file (Tier B badges), a pin record with freshness (3 commits behind) and 40
                     Python `public-api` items from two packages. The three verifier Gaps items of D14 arrive with `--verify` (Phase 4).

The names are made up and the paths are real tracked files of the repository, so every citation resolves.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import m3_page  # noqa: E402

COMPONENTS = 15
AREAS, PER_AREA, MODULES_PER_COMPONENT, IMPORTS, API_NAMES = 15, 4, 7, 1200, 40


def catalog(source: list, count: int = COMPONENTS) -> dict:
    """A `components` report whose catalog card names `count` components, each owning the files of one slice of `source`."""
    files = [p for p in source if p.endswith(".py")][:40]
    size = max(1, len(files) // count)
    rows = [{"cells": [f"Part{i:02d}", ", ".join(files[i * size:(i + 1) * size])]} for i in range(count) if files[i * size:(i + 1) * size]]
    return {"report": "components", "cards": [{"card": "components.catalog", "blocks": [{"type": "table", "headers": ["Component", "Paths"], "rows": rows}],
                                              "cite": ["facts:history"]}]}


def extend_small(out: Path, sha: str, source: list) -> None:
    (out / "reports" / "components.json").write_text(json.dumps(catalog(source)))


def large_modules() -> list:
    """(area, component, path) of 400 made-up modules: 15 areas of 4 components, 6 or 7 modules each."""
    out = []
    for a in range(AREAS):
        for c in range(PER_AREA):
            for m in range(MODULES_PER_COMPONENT):
                if len(out) < 400:
                    out.append((a, c, f"src/pkg/area{a:02d}/comp{c}/mod{m}.py"))
    return out


def large_graph(modules: list) -> list:
    """Module and import items. Three imports in five stay inside the area, so the graph has clusters and some links to filter."""
    items = [{"kind": "module", "path": "src/pkg/__init__.py", "module": "pkg", "package": "pkg", "is_package": True}]
    items += [{"kind": "module", "path": p, "module": p[:-3].replace("/", "."), "package": "pkg", "is_package": False} for _, _, p in modules]
    n = len(modules)
    for i in range(IMPORTS):
        a = modules[(i * 7) % n]
        j = (i * 13 + 5) % n
        if i % 5 < 3:  # same area
            same = [k for k, m in enumerate(modules) if m[0] == a[0]]
            j = same[(i * 3 + 1) % len(same)]
        b = modules[j]
        if a[2] == b[2]:
            b = modules[(j + 1) % n]
        items.append({"kind": "import", "path": a[2], "paths": [b[2]], "from": a[2][:-3].replace("/", "."), "to": b[2][:-3].replace("/", "."), "lines": [1 + i % 9], "via": "grimp"})
    return items


def large_catalog(modules: list) -> dict:
    rows = [{"cells": [f"Area{a:02d} part {c}", f"src/pkg/area{a:02d}/comp{c}/"]} for a in range(AREAS) for c in range(PER_AREA)]
    return {"report": "components", "cards": [{"card": "components.catalog", "blocks": [{"type": "table", "headers": ["Component", "Paths"], "rows": rows}],
                                              "cite": ["facts:history"]}]}


def python_api(files: list) -> list:
    out = []
    for i in range(API_NAMES):
        package = "m6lib" if i < 25 else "m6tools"
        out.append({"kind": "public-api", "path": files[i % len(files)], "line": 2 + i, "name": f"name_{i:02d}" if i % 2 else f"Class{i:02d}", "symbol_kind": "function" if i % 2 else "class",
                    "package": package, "subpath": f"{package}.api{i % 4}", "audience": "listed in __all__" if i % 3 else "public by name, typed", "external": None})
    return out


def pin_and_tools(out: Path, sha: str) -> None:
    """A build record with a pin that is 3 commits behind, and Shell and Rust among the languages (Tier B badges on eight cards)."""
    import buildlog

    path = buildlog.start(out, repo=str(m3_page.TOP), sha=sha, ref="main", version="1.0.0", options={})
    fresh = {"source": "remote", "remote_sha": "f" * 40, "compared_with": "origin/main", "behind": 3, "ahead": 0, "checked_at": "2026-11-09 10:00", "ref_kind": "branch"}
    buildlog.append(path, {"step": "pin", "by": "prepare", "status": "ok", "details": {"sha": sha, "ref": "main", "trust": {"trusted": True, "why": "on the default branch"}, "freshness": fresh}})
    langs = [{"name": "Python", "tier": "A", "files": 400}, {"name": "Shell", "tier": "B", "files": 2}, {"name": "Rust", "tier": "B", "files": 1}]
    buildlog.append(path, {"step": "tools", "by": "prepare", "status": "ok", "details": {"languages": langs, "missing": [], "self_installing": []}})
    facts = json.loads((out / "facts.json").read_text())
    have = {x["name"] for x in facts["languages"]}  # the fixture already counts Shell; Python and Rust are added
    facts["languages"] += [{"name": n, "kind": "code", "files": f, "lines": 10 * f, "bytes": 300 * f, "share_pct": 1.0} for n, f in (("Python", 400), ("Rust", 1)) if n not in have]
    (out / "facts.json").write_text(json.dumps(facts))


def extend_large(out: Path, sha: str, source: list) -> None:
    modules = large_modules()
    m3_page_add = __import__("m4_page")._add
    m3_page_add(out, "graph", sha, "python", large_graph(modules))
    m3_page_add(out, "symbols", sha, "python", python_api([p for p in source if p.endswith(".py")] or source))
    (out / "reports" / "components.json").write_text(json.dumps(large_catalog(modules)))
    pin_and_tools(out, sha)


def make(tmp: Path) -> Path:
    return m3_page.make(tmp, extend=extend_large)


def make_small(tmp: Path) -> Path:
    return m3_page.make(tmp, extend=extend_small)


if __name__ == "__main__":
    import tempfile
    print(make_small(Path(tempfile.mkdtemp())))
