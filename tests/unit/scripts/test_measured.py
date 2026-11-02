import html as htmllib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent / "scripts"))
import measured  # noqa: E402


class Refs:
    def mark(self, cites):
        return ""


TREE = {"pyproject.toml", "README.md", "Makefile", "docs/index.md", "docs/guide.md", "tests/test_a.py", "tests/conftest.py", "tests/unit/test_b.py",
        "src/app/a.py", "src/app/migrations/0001_init.py", ".github/workflows/ci.yml", "scripts/run.sh", "config/app.toml", ".pre-commit-config.yaml"}
FILES = {
    "pyproject.toml": "[build-system]\nrequires = []\n\n[tool.ruff]\nline-length = 100\n\n[tool.black]\nx = 1\n",
    ".pre-commit-config.yaml": "repos:\n- id: ruff\n",
    ".github/workflows/ci.yml": "steps:\n- run: ruff check\n- run: pytest\n",
}
EXTRACT = {
    "tests": [{"kind": "test-file", "path": "tests/test_a.py"}, {"kind": "test-file", "path": "tests/unit/test_b.py"}],
    "models": [{"kind": "migration", "path": "src/app/migrations/0001_init.py"}],
    "entry_points": [{"path": "src/app/a.py"}, {"path": "src/app/a.py"}],
}
CTX = {"tree": TREE, "extract": EXTRACT, "read": FILES.get}


def rows_of(html):
    cells = lambda r: [htmllib.unescape(re.sub(r"</?(code|span)[^>]*>|<wbr>", "", c)) for c in re.findall(r"<td[^>]*>(.*?)</td>", r)]
    return [cells(r) for r in re.findall(r"<tr>(.*?)</tr>", html.split("<tbody>")[1])]


class TestReadingMap:
    def test_each_concern_lists_its_places(self):
        html = measured.body("reading.map", CTX, Refs())
        rows = {r[0]: r[1] for r in rows_of(html)}

        assert list(rows) == ["configuration", "tests", "build", "docs", "migrations", "CI", "entry points", "scripts"]
        assert "docs/" in rows["docs"] and "README.md" in rows["docs"]
        assert "tests/" in rows["tests"] and "tests/unit" not in rows["tests"]
        assert "src/app/migrations/" in rows["migrations"]
        assert rows["CI"] == ".github/"
        assert rows["entry points"].count("src/app/a.py") == 1

    def test_concern_with_nothing_says_none_found(self):
        html = measured.body("reading.map", {"tree": {"x.py"}, "extract": {}}, Refs())

        assert "none found" in rows_of(html)[0][1]

    def test_without_a_tree_the_placeholder_is_used(self):
        assert measured.body("reading.map", {}, Refs()) is None


class TestTooling:
    def test_tools_found_with_config_and_where_enforced(self):
        rows = {r[0]: r for r in rows_of(measured.body("conventions.tooling", CTX, Refs()))}

        assert set(rows) == {"ruff", "black", "pre-commit"}
        assert "pyproject.toml:4" in rows["ruff"][1]
        assert rows["ruff"][2].startswith("pre-commit") and ".github/workflows/ci.yml" in rows["ruff"][2]
        assert rows["black"][2] == "not enforced in the repository"

    def test_no_tools_gives_the_fixed_sentence(self):
        html = measured.body("conventions.tooling", {"tree": {"a.py"}, "read": lambda p: None}, Refs())

        assert "No formatter or linter configuration was found." in html


class TestViolations:
    GRAPH = [
        {"kind": "import", "path": "a.py", "paths": ["b.py"], "from": "a", "to": "b", "lines": [3]},
        {"kind": "import", "path": "b.py", "paths": ["a.py"], "from": "b", "to": "a", "lines": [5]},
        {"kind": "cycle", "path": "a.py", "paths": ["a.py", "b.py"], "modules": ["a", "b"]},
        {"kind": "contract", "path": ".importlinter", "contract": "layers", "type": "layers", "status": "broken",
         "violations": [{"from": "x.low", "to": "x.high", "path": "x/low.py", "line": 7}]},
        {"kind": "contract", "path": ".importlinter", "contract": "indep", "type": "independence", "status": "not-checked", "reason": "Not checked by dossier."},
    ]

    def test_cycle_violation_and_unchecked_contract_each_get_a_row(self):
        rows = rows_of(measured.body("interactions.violations", {"extract": {"graph": self.GRAPH}}, Refs()))

        assert [r[0] for r in rows] == ["import cycle", "breaks contract 'layers'", "contract not checked"]
        assert rows[0][3] == "a.py:3"
        assert rows[1][1:3] == ["x.low", "x.high"]
        assert rows[2][3] == "Not checked by dossier."

    def test_nothing_found_texts(self):
        none = measured.body("interactions.violations", {"extract": {"graph": []}}, Refs())
        kept = measured.body("interactions.violations", {"extract": {"graph": [{"kind": "contract", "status": "kept", "contract": "c"}]}}, Refs())

        assert "No import cycles were found, and the repository declares no layer rules." in none
        assert "No import cycles were found, and every declared contract is kept." in kept

    def test_repository_text_is_escaped(self):
        graph = [{"kind": "contract", "contract": "<b>x</b>", "status": "not-checked", "reason": "<script>"}]

        html = measured.body("interactions.violations", {"extract": {"graph": graph}}, Refs())

        assert "<script>" not in html and "<b>x</b>" not in html

    def test_without_graph_output_the_placeholder_is_used(self):
        assert measured.body("interactions.violations", {"extract": {}}, Refs()) is None


class TestBody:
    def test_unknown_card_is_not_drawn(self):
        assert measured.body("data.entities", CTX, Refs()) is None
