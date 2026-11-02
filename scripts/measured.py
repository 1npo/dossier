"""Bodies of the measured cards in reports 03 to 12: cards a script draws from `extract/` and the repository, not Claude (D8).

`body(card_id, ctx, refs)` returns the HTML of the card, or None when this module does not draw it (or its input is missing),
so the page falls back to its placeholder. `ctx` carries `extract` (`{output: [items]}`), `tree` (tracked paths),
`read` (a function from a path to its text at the pinned commit, or None) and, for the graph cards, `catalog`.
"""
from __future__ import annotations

import re

import gather
import measured_graph


def _render():
    import render  # imported late: render imports this module

    return render


def _table(cid, columns, rows, refs):
    return _render().render_table(columns, rows, refs, "t-" + cid.replace(".", "-"), plain=True)


def _paths(paths, refs):
    r = _render()
    return ", ".join(r.path_cell(p, refs) for p in paths) if paths else '<span class="muted">none found</span>'


# ------------------------------------------------------------------ reading.map


def _rollup(matched: set, tree: set) -> list:
    """Folders whose every tracked file matched (the highest such folders), then the matched files left over."""
    under: dict = {}
    for p in tree:
        parts = p.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            under.setdefault("/".join(parts[:i]), []).append(p)
    full = sorted(d for d, fs in under.items() if all(f in matched for f in fs))
    top = [d for d in full if not any(d.startswith(o + "/") for o in full)]
    rest = sorted(p for p in matched if not any(p.startswith(d + "/") for d in top))
    return [d + "/" for d in top] + rest


def _shallowest(dirs: set) -> list:
    return sorted(d for d in dirs if not any(d.startswith(o + "/") for o in dirs if o and o != d))


def _is_config(p: str) -> bool:
    base = p.rsplit("/", 1)[-1]
    return (p in ("pyproject.toml", "setup.cfg", ".env.example") or base.endswith(".ini") or (base.endswith(".toml") and not p.startswith(".github/"))
            or p.startswith("config/") or "/config/" in p or bool(re.fullmatch(r"settings.*\.py", base)))


def _is_build(p: str) -> bool:
    base = p.rsplit("/", 1)[-1]
    return p in ("pyproject.toml", "setup.py", "Makefile", "noxfile.py", "tox.ini") or base.startswith("Dockerfile")


def _is_ci(p: str) -> bool:
    return p.startswith((".github/workflows/", ".circleci/")) or p in (".gitlab-ci.yml", "Jenkinsfile")


def _reading_map(cid, ctx, refs):
    tree = set(ctx.get("tree") or ())
    if not tree:
        return None
    extract = ctx.get("extract") or {}
    tests = {t["path"] for t in extract.get("tests", []) if t.get("kind") == "test-file"}
    test_places = [d + "/" for d in _shallowest({p.rsplit("/", 1)[0] for p in tests if "/" in p})] + sorted(p for p in tests if "/" not in p) if tests else \
        _rollup({p for p in tree if gather.TEST_RE.search(p)}, tree)
    read = ctx.get("read")

    def build_system(p):
        if p != "pyproject.toml" or read is None:
            return True
        return "[build-system]" in (read(p) or "")
    migrations = {m["path"].rsplit("/", 1)[0] for m in extract.get("models", []) if m.get("kind") == "migration" and "/" in m["path"]}
    rows = [
        ("configuration", _rollup({p for p in tree if _is_config(p)}, tree)),
        ("tests", test_places),
        ("build", _rollup({p for p in tree if _is_build(p) and build_system(p)}, tree)),
        ("docs", _rollup({p for p in tree if p.startswith("docs/") or ("/" not in p and p.endswith(".md"))}, tree)),
        ("migrations", [d + "/" for d in _shallowest(migrations)]),
        ("CI", _rollup({p for p in tree if _is_ci(p)}, tree)),
        ("entry points", sorted({e["path"] for e in extract.get("entry_points", []) if e.get("path")})),
        ("scripts", _rollup({p for p in tree if p.startswith(("scripts/", "bin/"))}, tree)),
    ]
    return _table(cid, ["Concern", "Location"], [[name, _paths(found, refs)] for name, found in rows], refs)


# ------------------------------------------------------------------ conventions.tooling

# tool -> (config files, section markers looked for in pyproject.toml / setup.cfg / tox.ini)
TOOLS = {
    "ruff": (("ruff.toml", ".ruff.toml"), ("[tool.ruff",)),
    "black": ((), ("[tool.black]",)),
    "isort": ((".isort.cfg",), ("[tool.isort]",)),
    "flake8": ((".flake8",), ("[flake8]",)),
    "mypy": (("mypy.ini", ".mypy.ini"), ("[tool.mypy]",)),
    "pyright": (("pyrightconfig.json",), ("[tool.pyright]",)),
    "pylint": ((".pylintrc",), ("[tool.pylint",)),
    "pre-commit": ((".pre-commit-config.yaml",), ()),
    "editorconfig": ((".editorconfig",), ()),
}
SHARED = ("pyproject.toml", "setup.cfg", "tox.ini")
NOT_ENFORCED = "not enforced in the repository"


def _line_of(text: str, marker: str) -> int | None:
    for n, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith(marker):
            return n
    return None


def _tooling(cid, ctx, refs):
    tree, read = set(ctx.get("tree") or ()), ctx.get("read")
    if not tree or read is None:
        return None
    texts = {p: (read(p) or "") for p in SHARED if p in tree}
    ci = sorted(p for p in tree if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml")) or p == ".gitlab-ci.yml")
    hooks = read(".pre-commit-config.yaml") or "" if ".pre-commit-config.yaml" in tree else ""
    r = _render()
    rows = []
    for tool, (files, sections) in TOOLS.items():
        where = [(f, None) for f in files if f in tree]
        for p, text in texts.items():
            for marker in sections + (("[flake8]",) if tool == "flake8" and p != "pyproject.toml" else ()):
                n = _line_of(text, marker)
                if n:
                    where.append((p, n))
                    break
        if not where:
            continue
        name = re.compile(r"(?<![\w-])" + re.escape(tool) + r"(?![\w-])", re.I)
        enforced = (["pre-commit"] if tool != "pre-commit" and name.search(hooks) else []) + [r.path_cell(p, refs) for p in ci if name.search(read(p) or "")]
        rows.append([tool, ", ".join(r.path_cell(p, refs, n) for p, n in where), ", ".join(enforced) if enforced else NOT_ENFORCED])
    if not rows:
        return '<p class="muted">No formatter or linter configuration was found.</p>'
    return _table(cid, ["Tool", "Config file", "Enforced where"], rows, refs)


# ------------------------------------------------------------------ interactions.violations


def _evidence(path, line, refs):
    return _render().path_cell(path, refs, line) if path else "-"


def _violations(cid, ctx, refs):
    extract = ctx.get("extract") or {}
    graph = extract.get("graph")
    if graph is None:
        return None
    E = _render().E
    imports = [g for g in graph if g.get("kind") == "import"]
    rows = []
    for cyc in (g for g in graph if g.get("kind") == "cycle"):
        mods = cyc["modules"]
        inside = [g for g in imports if g["from"] in mods and g["to"] in mods and g.get("lines")]
        first = min(inside, key=lambda g: (g["path"], g["lines"][0])) if inside else None
        rows.append(["import cycle", E(mods[0]), E(" → ".join(mods[1:] + mods[:1])),
                     _evidence(first["path"], first["lines"][0], refs) if first else _evidence(cyc["path"], None, refs)])
    contracts = [g for g in graph if g.get("kind") == "contract"]
    for c in contracts:
        if c["status"] == "broken":
            for v in c.get("violations") or []:
                rows.append([E(f"breaks contract '{c['contract']}'"), E(v["from"]), E(v["to"]), _evidence(v.get("path"), v.get("line"), refs)])
        elif c["status"] == "not-checked":
            rows.append(["contract not checked", E(c["contract"]), "-", E(c.get("reason") or "")])
    if rows:
        return _table(cid, ["Kind", "From", "To", "Evidence"], rows, refs)
    tail = ", and every declared contract is kept" if contracts else ", and the repository declares no layer rules"
    return f'<p class="muted">No import cycles were found{tail}.</p>'


DRAWN = {"reading.map": _reading_map, "conventions.tooling": _tooling, "interactions.violations": _violations, **measured_graph.DRAWN}


def body(cid: str, ctx: dict, refs):
    draw = DRAWN.get(cid)
    return draw(cid, ctx or {}, refs) if draw else None
