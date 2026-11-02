import html as htmllib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent / "scripts"))
import measured  # noqa: E402
import measured_graph  # noqa: E402


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


class TestMermaidId:
    def test_unsafe_characters_become_underscores(self):
        assert measured_graph.mermaid_id("a-b.c") == "a_b_c"

    def test_leading_digit_gets_a_prefix(self):
        assert measured_graph.mermaid_id("3d") == "n_3d"

    def test_two_names_never_share_an_id(self):
        taken = {}

        first = measured_graph.mermaid_id("a-b", taken)
        second = measured_graph.mermaid_id("a.b", taken)

        assert first != second


def imp(a, b, lines=(1,)):
    return {"kind": "import", "path": a, "paths": [b], "from": a[:-3].replace("/", "."), "to": b[:-3].replace("/", "."), "lines": list(lines)}


MAP_EXTRACT = {"graph": [
    {"kind": "module", "path": "src/app/__init__.py", "module": "app", "package": "app", "is_package": True},
    imp("src/app/api/x.py", "src/app/core/y.py", (2, 9)), imp("src/app/api/x.py", "src/app/db/z.py"), imp("src/app/db/z.py", "src/app/core/y.py"),
    imp("src/app/core/y.py", "loose.py", (4,)),
]}
MAP_CTX = {"extract": MAP_EXTRACT, "tree": {"src/app/api/x.py", "src/app/core/y.py", "src/app/db/z.py", "loose.py"},
           "catalog": [{"name": "Api", "paths": ["src/app/api/"]}, {"name": "Core", "paths": ["src/app/core/"]}, {"name": "Db", "paths": ["src/app/db/"]}],
           "facts": {"chunks": {"chunks": [{"files": [{"path": "src/app/api/x.py", "lines": 10}]}]}}}


def table_html(html, tid):
    return re.search(r'<table class="table[^"]*" id="%s".*?</table>' % re.escape(tid), html, re.S).group(0)


def mermaid_source(html):
    return htmllib.unescape(re.search(r'data-src="([^"]*)"', html).group(1))


class TestComponentMap:
    def test_one_subgraph_per_area_and_one_node_per_component(self):
        src = mermaid_source(measured.body("components.map", MAP_CTX, Refs()))

        assert src.startswith("flowchart TB")
        assert src.count("subgraph") == 4  # api, core, db and the unassigned loose module
        assert 'Api["Api"]' in src and 'Core["Core"]' in src and 'Db["Db"]' in src

    def test_arrows_carry_no_labels_and_unassigned_is_a_group(self):
        src = mermaid_source(measured.body("components.map", MAP_CTX, Refs()))

        assert "Api --> Core" in src and "Core --> unassigned" in src
        assert "-->|" not in src

    def test_table_has_files_lines_and_neighbours(self):
        rows = {r[0]: r for r in rows_of(table_html(measured.body("components.map", MAP_CTX, Refs()), "t-components-map"))}

        assert rows["Api"][1:] == ["api", "1", "10", "Core, Db", "-"]
        assert rows["Core"][5] == "Api, Db"

    def test_without_a_catalog_the_placeholder_is_used(self):
        assert measured.body("components.map", {"extract": MAP_EXTRACT}, Refs()) is None


class TestDependencyGraph:
    def test_table_has_one_row_per_import(self):
        html = measured.body("interactions.graph", MAP_CTX, Refs())

        rows = rows_of(table_html(html, "t-interactions-graph-edges"))
        assert len(rows) == 4
        assert rows[0] == ["Api", "Core", "src.app.api.x", "src.app.core.y", "2", "src/app/api/x.py:2, src/app/api/x.py:9"]

    def test_without_a_catalog_nodes_are_areas(self):
        src = mermaid_source(measured.body("interactions.graph", {"extract": MAP_EXTRACT}, Refs()))

        assert 'api["api"]' in src and "api --> core" in src

    def test_a_single_node_draws_only_the_table(self):
        extract = {"graph": [imp("a.py", "b.py")]}

        html = measured.body("interactions.graph", {"extract": extract}, Refs())

        assert "mermaid-host" not in html and "<table" in html

    def test_no_imports_says_so(self):
        assert "No imports between modules were found." in measured.body("interactions.graph", {"extract": {"graph": []}}, Refs())


class TestComponentArea:
    ROOTS = ["src/cannalerts"]

    def test_files_in_the_package_root_are_its_top_level_modules(self):
        paths = ["src/cannalerts/cli.py", "src/cannalerts/__main__.py"]

        assert measured_graph.component_area(paths, self.ROOTS) == "cannalerts (top-level modules)"

    def test_a_folder_below_the_package_root_is_the_area(self):
        assert measured_graph.component_area(["src/cannalerts/platforms/dutchie/"], self.ROOTS) == "platforms"

    def test_files_in_one_folder_are_that_folder(self):
        paths = ["src/cannalerts/platforms/__init__.py", "src/cannalerts/platforms/base.py"]

        assert measured_graph.component_area(paths, self.ROOTS) == "platforms"

    def test_a_path_outside_any_package_uses_its_top_folder(self):
        assert measured_graph.component_area(["tests/"], self.ROOTS) == "tests"

    def test_a_file_at_the_repository_root_has_its_own_area_name(self):
        assert measured_graph.component_area(["setup.py"], self.ROOTS) == "(repository root)"

    def test_no_paths_is_the_repository_root(self):
        assert measured_graph.component_area([], self.ROOTS) == "(repository root)"

    def test_paths_in_two_folders_use_the_first_path(self):
        paths = ["src/cannalerts/db/a.py", "src/cannalerts/core/b.py"]

        assert measured_graph.component_area(paths, self.ROOTS) == "db"


class TestComponentMapAreas:
    def test_area_column_names_folders_not_files(self):
        extract = {"graph": [
            {"kind": "module", "path": "src/app/__init__.py", "module": "app", "package": "app", "is_package": True},
            imp("src/app/cli.py", "src/app/models.py"),
        ]}
        ctx = {"extract": extract, "tree": {"src/app/cli.py", "src/app/models.py"},
               "catalog": [{"name": "Cli", "paths": ["src/app/cli.py"]}, {"name": "Models", "paths": ["src/app/models.py"]}]}

        rows = rows_of(table_html(measured.body("components.map", ctx, Refs()), "t-components-map"))

        assert {r[1] for r in rows} == {"app (top-level modules)"}


def big_graph(components=16, areas=6, edges=71):
    names = [f"C{i:02d}" for i in range(components)]
    area = {n: f"area{i % areas}" for i, n in enumerate(names)}
    pairs = [(a, b) for a in names for b in names if a != b]
    chosen = {pair: 1 + i % 3 for i, pair in enumerate(pairs[::3][:edges])}
    assert len(chosen) == edges
    return chosen, area


def sources(result):
    return [src for _, src, _ in result]


def node_count(src):
    return len(re.findall(r'^\s+\w+\["', src, re.M))


def edge_count(src):
    return len(re.findall(r"^\s+\w+ --> \w+$", src, re.M))


class TestDiagrams:
    def test_a_small_graph_is_one_diagram(self):
        edges = {("A", "B"): 2, ("B", "C"): 1, ("A", "C"): 1, ("C", "D"): 1, ("D", "E"): 1, ("E", "A"): 1}
        area = {"A": "x", "B": "x", "C": "y", "D": "y", "E": "y"}

        result = measured_graph.diagrams(edges, area)

        assert len(result) == 1
        assert result[0][2] == ""

    def test_a_big_graph_is_split_into_an_overview_and_one_diagram_per_area(self):
        edges, area = big_graph()

        result = measured_graph.diagrams(edges, area)

        assert len(result) == 1 + 6
        assert {budget for _, _, budget in result} == {"area"}

    def test_every_diagram_is_drawn_without_edge_labels(self):
        edges, area = big_graph()

        result = measured_graph.diagrams(edges, area)

        assert not any("-->|" in src for src in sources(result))

    def test_every_component_edge_appears_in_an_area_diagram_or_the_overview(self):
        edges, area = big_graph()
        result = {t: s for t, s, _ in measured_graph.diagrams(edges, area)}
        ids = {title: dict((label, i) for i, label in re.findall(r'^\s+(\w+)\["([^"]*)"\]', src, re.M)) for title, src in result.items()}
        arrows = {title: set(re.findall(r"^\s+(\w+) --> (\w+)$", src, re.M)) for title, src in result.items()}
        overview = next(t for t in result if t.endswith("areas"))

        for (a, b) in edges:
            if area[a] == area[b]:
                assert any((ids[t][a], ids[t][b]) in arrows[t] for t in result if a in ids[t] and b in ids[t]), (a, b)
            else:
                assert (ids[overview][area[a]], ids[overview][area[b]]) in arrows[overview], (a, b)
                assert any((ids[t][a], ids[t][area[b] + " (area)"]) in arrows[t] for t in result if a in ids[t] and area[b] + " (area)" in ids[t]), (a, b)
                assert any((ids[t][area[a] + " (area)"], ids[t][b]) in arrows[t] for t in result if b in ids[t] and area[a] + " (area)" in ids[t]), (a, b)

    def test_the_overview_has_one_node_per_area(self):
        edges, area = big_graph()

        overview = next(src for title, src, _ in measured_graph.diagrams(edges, area) if title.endswith("areas"))

        assert node_count(overview) == 6

    def test_isolated_components_are_still_drawn(self):
        edges, area = big_graph()
        area["Lonely"] = "area0"

        result = measured_graph.diagrams(edges, area, extra=["Lonely"])

        assert any('Lonely["Lonely"]' in src for src in sources(result))

    def test_without_areas_an_oversized_graph_is_one_diagram_marked_over_budget(self):
        edges, _ = big_graph()

        result = measured_graph.diagrams(edges, None)

        assert len(result) == 1
        assert result[0][2] == "area"


class TestHostBudgetMark:
    def test_budget_is_set_on_the_host_only_when_given(self):
        marked = measured_graph._diagram("T", "flowchart TB\n  a --> b", "area")
        plain = measured_graph._diagram("T", "flowchart TB\n  a --> b")

        assert 'data-budget="area"' in marked
        assert "data-budget" not in plain


def big_ctx():
    edges, area = big_graph()
    names = sorted(area)
    files = {n: f"src/app/{area[n]}/{n.lower()}/m.py" for n in names}
    graph = [{"kind": "module", "path": "src/app/__init__.py", "module": "app", "package": "app", "is_package": True}]
    for (a, b), count in edges.items():
        for k in range(count):
            graph.append(imp(files[a], files[b].replace("m.py", f"m_{k}.py")))
    catalog = [{"name": n, "paths": [files[n].rsplit("/", 1)[0] + "/"]} for n in names]
    tree = set(files.values())
    return {"extract": {"graph": graph}, "tree": tree, "catalog": catalog, "facts": {}}, edges, area


class TestComponentTables:
    def test_matrix_has_one_row_and_column_per_component_and_every_edge_count(self):
        ctx, edges, _ = big_ctx()

        html = measured.body("components.map", ctx, Refs())
        matrix = table_html(html, "t-components-map-matrix")
        header = re.findall(r"<th(?: [^>]*)?>(.*?)</th>", matrix.split("<tbody>")[0])
        rows = rows_of(matrix)

        assert len(header) == 1 + 16
        assert len(rows) == 16
        cells = {(r[0], header[i + 1]): int(c) for r in rows for i, c in enumerate(r[1:]) if c}
        assert cells == {pair: n for pair, n in edges.items()}

    def test_matrix_is_marked_unsortable_and_styled_as_a_matrix(self):
        ctx, _, _ = big_ctx()

        matrix = table_html(measured.body("components.map", ctx, Refs()), "t-components-map-matrix")

        assert 'class="table dsm"' in matrix and "data-nosort" in matrix

    def test_component_edge_table_has_every_edge_most_imports_first(self):
        ctx, edges, _ = big_ctx()

        rows = rows_of(table_html(measured.body("interactions.graph", ctx, Refs()), "t-interactions-graph-components"))

        assert len(rows) == len(edges) == 71
        counts = [int(r[2]) for r in rows]
        assert counts == sorted(counts, reverse=True)

    def test_module_table_has_a_row_per_import_and_leads_with_the_components(self):
        ctx, _, _ = big_ctx()
        html = measured.body("interactions.graph", ctx, Refs())
        table = table_html(html, "t-interactions-graph-edges")

        headers = re.findall(r"<th(?: [^>]*)?>(.*?)</th>", table.split("<tbody>")[0])
        rows = rows_of(table)

        assert headers[:2] == ["From component", "To component"]
        assert len(rows) == sum(1 for g in ctx["extract"]["graph"] if g["kind"] == "import")

    def test_a_graph_within_the_budget_is_one_diagram(self):
        html = measured.body("components.map", MAP_CTX, Refs())

        assert html.count('class="mermaid-host"') == 1

    def test_a_big_graph_draws_an_overview_and_area_diagrams(self):
        ctx, _, _ = big_ctx()

        html = measured.body("components.map", ctx, Refs())

        assert html.count('class="mermaid-host"') == 7
        assert html.count('data-budget="area"') == 7
