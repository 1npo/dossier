"""Build a page that holds what M4 adds, for the V11 and V12 tests (plan 010, M4-24).

  make(tmp) -> Path to the rendered page

It is the M3 page (`m3_page.make`) plus extractor output for JavaScript: 60 React components that render one another, a Prisma model
set, knip findings, and a public API of three packages. The names are made up and the paths are real tracked files of the repository, so
every citation resolves. Nothing real is read except the file list. The tables are far taller than 40 rows, as on a real React repository.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import m3_page  # noqa: E402

COMPONENTS = 60


def _add(out: Path, name: str, sha: str, adapter: str, items: list) -> None:
    """Add a section for `adapter` to extract/<name>.json, keeping the sections that are there."""
    f = out / "extract" / f"{name}.json"
    data = json.loads(f.read_text()) if f.exists() else {"schema": 1, "sha": sha, "adapters": {}}
    data["adapters"][adapter] = {"sha": sha, "version": "1", "tools": {}, "tool_status": {}, "items": items}
    f.write_text(json.dumps(data))


def components(files: list) -> list:
    """`ui-component` and `renders` graph items: component i renders component i+1 and, every fifth one, component i+2."""
    items, names = [], [f"Component{i:02d}" for i in range(COMPONENTS)]
    for i, (path, name) in enumerate(zip(files, names)):
        items.append({"kind": "ui-component", "path": path, "line": 3 + i % 7, "end_line": 12 + i % 7, "name": name, "exported": i % 4 != 0,
                      "hooks": ["useState", "useEffect"][: i % 3], "provides": [f"Theme{i}Context"] if i % 10 == 0 else [], "consumes": ["UserContext"] if i % 6 == 0 else []})
        for step in (1, 2) if i % 5 == 0 else (1,):
            if i + step < COMPONENTS:
                items.append({"kind": "renders", "path": path, "paths": [files[i + step]], "from": name, "to": names[i + step]})
    return items


def prisma_models() -> list:
    def field(name, typ, line, ref=None, pk=False):
        return {"name": name, "type": typ, "line": line, "ref": ref, "pk": pk}
    path = "prisma/schema.prisma"
    models = [("User", [field("id", "Int", 3, pk=True), field("email", "String", 4), field("posts", "Post[]", 5, "Post")]),
              ("Post", [field("id", "Int", 9, pk=True), field("title", "String", 10), field("author", "User", 11, "User"), field("status", "Status", 12, "Status")]),
              ("Tag", [field("id", "Int", 16, pk=True), field("name", "String", 17)])]
    items = [{"path": path, "line": fields[0]["line"] - 1, "end_line": fields[-1]["line"] + 1, "name": n, "kind": "prisma", "rule": "prisma", "snippet": f"model {n} {{",
              "bases": [], "fields": fields} for n, fields in models]
    items.append({"path": path, "line": 20, "end_line": 24, "name": "Status", "kind": "prisma-enum", "rule": "prisma-enum", "snippet": "enum Status {", "bases": [],
                  "fields": [field("Draft", "", 21), field("Published", "", 22)]})
    return items


def knip_rows(files: list) -> list:
    rows = [(files[i], "knip.files", "unused file", files[i], "No entry point or other file uses this file.") for i in range(5)]
    rows += [("package.json", "knip.dependencies", "unused dependency", n, "Listed in package.json, but no file imports it.") for n in ("left-pad", "lodash")]
    rows += [(files[5 + i], "knip.exports", "unused export", f"helper{i}", "Exported, but nothing imports it.") for i in range(3)]
    return [{"path": p, "line": None, "end_line": None, "type": t, "name": n, "message": m, "confidence": None, "rule": r, "snippet": n} for p, r, t, n, m in rows]


def public_api(files: list) -> list:
    out = []
    for package, subpath, start in (("@demo/ui", ".", 0), ("@demo/ui", "./forms", 10), ("@demo/core", ".", 20)):
        for i in range(8):
            out.append({"kind": "public-api", "path": files[start + i], "line": 2 + i, "name": f"api{start + i:02d}", "symbol_kind": ("function", "class", "type")[i % 3],
                        "package": package, "subpath": subpath, "audience": "not marked private" if package == "@demo/ui" else "marked private"})
    return out


def extend(out: Path, sha: str, source: list) -> None:
    files = [p for p in source if "/" in p][: COMPONENTS + 10] or source[: COMPONENTS + 10]
    _add(out, "graph", sha, "js", components(files))
    _add(out, "models", sha, "js", prisma_models())
    _add(out, "dead", sha, "js", knip_rows(files))
    _add(out, "symbols", sha, "js", public_api(files))
    reports = out / "reports" / "io.json"
    data = json.loads(reports.read_text()) if reports.exists() else {"report": "io", "cards": []}
    data["cards"] = [c for c in data.get("cards", []) if c.get("card") != "io.contracts"] + [
        {"card": "io.contracts", "na": "The fixture page does not write this card.", "cite": ["facts:history"]}]
    reports.write_text(json.dumps(data))


def make(tmp: Path) -> Path:
    return m3_page.make(tmp, extend=extend)


if __name__ == "__main__":
    import tempfile
    print(make(Path(tempfile.mkdtemp())))
