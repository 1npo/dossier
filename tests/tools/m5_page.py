"""Build a page that holds what M5 adds, for the V11 and V12 tests (plan 011, M5-27).

  make(tmp) -> Path to the rendered page

It is the M3 page (`m3_page.make`) plus extractor output for C#: a public API of 80 names in two packable libraries, three
`InternalsVisibleTo` friends, 20 EF Core entities that refer to one another, unreferenced-type rows and projects for two
target frameworks (so the upgrade-burden table has .NET rows). The names are made up and the paths are real tracked files of
the repository, so every citation resolves. Nothing real is read except the file list.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import m3_page  # noqa: E402
from m4_page import _add  # noqa: E402

ENTITIES = 20
API_NAMES = 80


def projects() -> list:
    def project(name, frameworks, test=False, packable=False, friends=()):
        return {"kind": "cs-project", "path": f"src/{name}/{name}.csproj", "name": name, "sdk": "Microsoft.NET.Sdk", "output_type": "Library", "frameworks": frameworks,
                "test": test, "packable": packable, "references": [], "friends": list(friends)}
    return [project("Demo.Core", ["net10.0"], packable=True, friends=["Demo.Core.Tests", "Demo.Bench"]),
            project("Demo.Data", ["net8.0", "net10.0"], packable=True, friends=["Demo.Data.Tests"]),
            project("Demo.Core.Tests", ["net10.0"], test=True)]


def modules(files: list) -> list:
    return [{"kind": "module", "path": p, "module": p[:-3] if p.endswith(".py") else p, "short": p.rsplit("/", 1)[-1].split(".")[0], "namespaces": ["Demo"],
             "project": "src/Demo.Core/Demo.Core.csproj", "language": "csharp", "generated": False, "complexity": 1} for p in files[:10]]


def public_api(files: list) -> list:
    out = []
    for i in range(API_NAMES):
        library = "Demo.Core" if i < 50 else "Demo.Data"
        out.append({"kind": "public-api", "path": files[i % len(files)], "line": 2 + i, "name": f"Type{i:02d}" if i % 3 == 0 else f"Type{i - i % 3:02d}.Member{i:02d}",
                    "symbol_kind": ("class", "method", "property")[i % 3], "package": library, "subpath": f"{library}.Api{i % 4}", "audience": "packable"})
    return out


def entities(files: list) -> list:
    items = []
    for i in range(ENTITIES):
        fields = [{"name": "Id", "type": "int", "line": 4 + i, "ref": None, "pk": True, "many": False},
                  {"name": "Name", "type": "string", "line": 5 + i, "ref": None, "pk": False, "many": False}]
        relations = []
        if i + 1 < ENTITIES:
            fields.append({"name": "Next", "type": f"Entity{i + 1:02d}", "line": 6 + i, "ref": f"Entity{i + 1:02d}", "pk": False, "many": False})
            relations.append({"field": "Next", "to": f"Entity{i + 1:02d}", "kind": "ef"})
        items.append({"path": files[i % len(files)], "line": 3 + i, "end_line": 8 + i, "name": f"Entity{i:02d}", "kind": "ef-entity", "rule": "cs.ef-entity",
                      "snippet": f"class Entity{i:02d}", "bases": [], "fields": fields, "relations": relations})
    return items


def dead(files: list) -> list:
    text = "Nothing references this type. Whether to remove it is for the reader to decide."
    return [{"path": files[i], "line": 3, "end_line": 9, "type": "dead code without references", "name": f"Unused{i}", "message": text, "confidence": None,
             "rule": "scip-dotnet.unused-type", "snippet": text} for i in range(6)]


def extend(out: Path, sha: str, source: list) -> None:
    files = [p for p in source if "/" in p][:API_NAMES] or source[:API_NAMES]
    _add(out, "graph", sha, "csharp", modules(files) + projects())
    _add(out, "models", sha, "csharp", entities(files))
    _add(out, "dead", sha, "csharp", dead(files))
    _add(out, "symbols", sha, "csharp", public_api(files))
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
