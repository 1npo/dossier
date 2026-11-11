import html as htmllib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent / "scripts"))
import measured  # noqa: E402
import measured_cs  # noqa: E402
import measured_graph  # noqa: E402


class Refs:
    def mark(self, cites):
        return ""


class MarkedRefs:
    """Writes each cited source as text, so a test can see what lands in a Source cell."""

    def mark(self, cites):
        return "".join(f"[{c}]" for c in dict.fromkeys(cites))


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
        rows = {}
        for concern, place, _ in rows_of(html):
            rows.setdefault(concern, []).append(place)

        assert list(rows) == ["configuration", "tests", "build", "docs", "migrations", "CI", "entry points", "scripts"]
        assert "docs/" in rows["docs"] and "README.md" in rows["docs"]
        assert "tests/" in rows["tests"] and "tests/unit" not in rows["tests"]
        assert rows["migrations"] == ["src/app/migrations/"]
        assert rows["CI"] == [".github/"]
        assert rows["entry points"] == ["src/app/a.py"]

    def test_one_row_for_each_concern_and_location_with_its_citation_in_source(self):
        rows = rows_of(measured.body("reading.map", CTX, MarkedRefs()))

        docs = [r for r in rows if r[0] == "docs"]
        assert len(docs) == 2
        assert all(len(r) == 3 for r in rows)
        assert {r[1]: r[2] for r in docs} == {"docs/": "[docs/]", "README.md": "[README.md]"}
        assert "[" not in "".join(r[1] for r in rows)

    def test_concern_with_nothing_says_none_found(self):
        html = measured.body("reading.map", {"tree": {"x.py"}, "extract": {}}, Refs())

        assert rows_of(html)[0][1:] == ["none found", ""]

    def test_without_a_tree_the_placeholder_is_used(self):
        assert measured.body("reading.map", {}, Refs()) is None


class TestTooling:
    def test_tools_found_with_config_and_where_enforced(self):
        rows = {r[0]: r for r in rows_of(measured.body("conventions.tooling", CTX, Refs()))}

        assert set(rows) == {"ruff", "black", "pre-commit"}
        assert rows["ruff"][1] == "pyproject.toml"
        assert rows["ruff"][2].startswith("pre-commit") and ".github/workflows/ci.yml" in rows["ruff"][2]
        assert rows["black"][2] == "not enforced in the repository"

    def test_citations_go_in_the_source_column(self):
        rows = {r[0]: r for r in rows_of(measured.body("conventions.tooling", CTX, MarkedRefs()))}

        assert rows["ruff"][3] == "[pyproject.toml:4][.github/workflows/ci.yml]"
        assert "[" not in rows["ruff"][1] + rows["ruff"][2]

    def test_no_tools_gives_the_fixed_sentence(self):
        html = measured.body("conventions.tooling", {"tree": {"a.py"}, "read": lambda p: None}, Refs())

        assert "No formatter or linter configuration was found." in html


JS_TREE = {"package.json", "package-lock.json", "tsconfig.json", ".eslintrc.cjs", ".prettierrc", ".husky/pre-commit", ".github/workflows/ci.yml",
           "nx.json", ".env.example", "apps/web/package.json", "apps/web/tsconfig.app.json", "apps/web/vite.config.ts", "apps/web/.env.example",
           "apps/web/src/main.tsx", "apps/web/jest.config.js", "libs/util/package.json", "libs/util/src/index.ts"}
JS_FILES = {
    "package.json": '{\n  "name": "root",\n  "scripts": {"build": "nx build"},\n  "eslintConfig": {"root": true},\n  "lint-staged": {"*.ts": "eslint"}\n}\n',
    "apps/web/package.json": '{"name": "web", "scripts": {"build": "vite build"}, "prettier": {"semi": false}}',
    "libs/util/package.json": '{"name": "util", "scripts": {"test": "jest"}}',
    ".husky/pre-commit": "npx lint-staged\n",
    ".github/workflows/ci.yml": "steps:\n- run: yarn eslint .\n- run: yarn tsc --noEmit\n",
}
JS_CTX = {"tree": JS_TREE, "extract": {}, "read": JS_FILES.get}


class TestJavaScriptReadingMap:
    def places(self, concern):
        return [r[1] for r in rows_of(measured.body("reading.map", JS_CTX, Refs())) if r[0] == concern]

    def test_configuration_includes_manifests_tsconfigs_env_examples_and_tool_configs_at_any_depth(self):
        got = self.places("configuration")

        for p in ("package.json", "tsconfig.json", ".env.example", "apps/web/package.json", "apps/web/tsconfig.app.json", "apps/web/.env.example",
                  "apps/web/vite.config.ts", "apps/web/jest.config.js", "libs/util/package.json"):
            assert p in got or any(g.endswith("/") and p.startswith(g) for g in got), p

    def test_build_includes_a_manifest_with_a_build_script_and_build_tool_configs(self):
        got = self.places("build")

        assert "package.json" in got and "apps/web/package.json" in got and "nx.json" in got and "apps/web/vite.config.ts" in got
        assert "libs/util/package.json" not in got

    def test_a_python_tree_gives_the_rows_it_gave_before(self):
        rows = rows_of(measured.body("reading.map", CTX, Refs()))

        assert [r[1] for r in rows if r[0] == "build"] == ["Makefile", "pyproject.toml"]
        assert [r[1] for r in rows if r[0] == "configuration"] == ["config/", "pyproject.toml"]


class TestJavaScriptTooling:
    def rows(self):
        return {r[0]: r for r in rows_of(measured.body("conventions.tooling", JS_CTX, Refs()))}

    def test_tools_are_found_by_config_file_at_any_depth(self):
        got = self.rows()

        assert {"eslint", "prettier", "typescript", "husky", "lint-staged"} <= set(got)
        assert "tsconfig.json" in got["typescript"][1] and "apps/web/tsconfig.app.json" in got["typescript"][1]

    def test_a_key_in_package_json_counts_and_names_that_file(self):
        got = self.rows()

        assert "package.json" in got["eslint"][1] and "apps/web/package.json" in got["prettier"][1]

    def test_ci_and_hooks_show_where_a_tool_is_enforced(self):
        got = self.rows()

        assert ".github/workflows/ci.yml" in got["eslint"][2] and ".github/workflows/ci.yml" in got["typescript"][2]
        assert "husky" in got["lint-staged"][2]
        assert got["prettier"][2] == "not enforced in the repository"

    def test_python_tools_still_come_first_and_unchanged(self):
        assert [r[0] for r in rows_of(measured.body("conventions.tooling", CTX, Refs()))] == ["ruff", "black", "pre-commit"]

    def test_a_package_json_that_is_not_json_is_skipped(self):
        ctx = {"tree": {"package.json"}, "read": {"package.json": "{ not json"}.get}

        assert "No formatter or linter configuration was found." in measured.body("conventions.tooling", ctx, Refs())


CS_TREE = {"global.json", "NuGet.Config", "Directory.Build.props", "Shop.sln", "build.cake", ".config/dotnet-tools.json", ".csharpierrc.json", ".editorconfig",
           "stylecop.json", "src/Api/Api.csproj", "src/Api/appsettings.json", "src/Api/appsettings.Development.json", "src/Api/Properties/launchSettings.json",
           "tests/Api.Tests/Api.Tests.csproj", "tests/Api.Tests/test.runsettings", "src/Data/Migrations/001_Init.cs", ".github/workflows/ci.yml", ".globalconfig",
           "src/Api/Program.cs"}
CS_FILES = {
    "Directory.Build.props": "<Project><PropertyGroup><EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild></PropertyGroup></Project>",
    "src/Api/Api.csproj": "<Project>\n<ItemGroup><PackageReference Include=\"StyleCop.Analyzers\" Version=\"1.0\" /></ItemGroup></Project>",
    ".config/dotnet-tools.json": '{\n "tools": {\n  "csharpier": {"version": "1"}}}',
    ".github/workflows/ci.yml": "steps:\n- run: dotnet format --verify-no-changes\n- run: dotnet csharpier --check .\n",
}
CS_CTX = {"tree": CS_TREE, "extract": {"models": [{"kind": "migration", "path": "src/Data/Migrations/001_Init.cs"}]}, "read": CS_FILES.get}


class TestCSharpFiles:
    def test_config_files_are_found_at_any_depth_and_any_case(self):
        for p in ("global.json", "nuget.config", "NuGet.Config", "src/A/appsettings.json", "src/A/appsettings.Production.json", "src/A/Properties/launchSettings.json",
                  "Directory.Build.props", "Directory.Build.targets", "Directory.Packages.props", "t/x.runsettings", ".config/dotnet-tools.json"):
            assert measured_cs.is_config(p), p

        assert not measured_cs.is_config("src/A/Program.cs") and not measured_cs.is_config("src/appsettings.cs")

    def test_build_files_are_solutions_projects_and_cake(self):
        for p in ("Shop.sln", "Shop.slnx", "src/A/A.csproj", "build.cake"):
            assert measured_cs.is_build(p), p

        assert not measured_cs.is_build("src/A/A.cs")


class TestCSharpReadingMap:
    def places(self, concern):
        return [r[1] for r in rows_of(measured.body("reading.map", CS_CTX, Refs())) if r[0] == concern]

    def test_configuration_and_build_include_the_dotnet_files(self):
        config, build = self.places("configuration"), self.places("build")

        assert "global.json" in config and "Directory.Build.props" in config and "NuGet.Config" in config
        assert "Shop.sln" in build and "build.cake" in build and "src/Api/Api.csproj" in build

    def test_the_ef_migrations_folder_appears(self):
        assert self.places("migrations") == ["src/Data/Migrations/"]


class TestCSharpTooling:
    def rows(self):
        return {r[0]: r for r in rows_of(measured.body("conventions.tooling", CS_CTX, Refs()))}

    def test_each_tool_is_found_by_its_file_or_key(self):
        got = self.rows()

        assert ".csharpierrc.json" in got["csharpier"][1] and ".config/dotnet-tools.json" in got["csharpier"][1]
        assert "Directory.Build.props" in got["dotnet-format"][1]
        assert "stylecop.json" in got["StyleCop"][1] and "src/Api/Api.csproj" in got["StyleCop"][1]
        assert ".globalconfig" in got[".globalconfig"][1]

    def test_ci_shows_where_dotnet_format_and_csharpier_are_enforced(self):
        got = self.rows()

        assert ".github/workflows/ci.yml" in got["dotnet-format"][2] and ".github/workflows/ci.yml" in got["csharpier"][2]
        assert got["StyleCop"][2] == "not enforced in the repository"

    def test_dotnet_format_needs_the_editorconfig_and_the_setting(self):
        ctx = {"tree": {".editorconfig", "Directory.Build.props"}, "read": {"Directory.Build.props": "<Project/>"}.get}
        rows = {r[0] for r in rows_of(measured.body("conventions.tooling", ctx, Refs()))}

        assert "dotnet-format" not in rows and "editorconfig" in rows

    def test_a_csharpier_entry_needs_the_tools_file_to_name_it(self):
        ctx = {"tree": {".config/dotnet-tools.json"}, "read": {".config/dotnet-tools.json": '{"tools": {"dotnet-ef": {}}}'}.get}

        assert "No formatter or linter configuration was found." in measured.body("conventions.tooling", ctx, Refs())

    def test_python_and_javascript_trees_give_the_rows_they_gave(self):
        assert [r[0] for r in rows_of(measured.body("conventions.tooling", CTX, Refs()))] == ["ruff", "black", "pre-commit"]


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

    def test_evidence_is_cited_in_the_source_column(self):
        rows = rows_of(measured.body("interactions.violations", {"extract": {"graph": self.GRAPH}}, MarkedRefs()))

        assert [r[4] for r in rows] == ["[a.py:3]", "[x/low.py:7]", ""]

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


class TestComponentMap:
    def test_draws_no_diagram_of_which_component_imports_which(self):
        html = measured.body("components.map", MAP_CTX, Refs())

        assert "mermaid-host" not in html and "flowchart" not in html

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
        assert rows[0] == ["Api", "Core", "src.app.api.x", "src.app.core.y", "2", ""]

    def test_module_table_cites_each_import_line_in_the_source_column(self):
        html = measured.body("interactions.graph", MAP_CTX, MarkedRefs())

        rows = rows_of(table_html(html, "t-interactions-graph-edges"))
        assert rows[0][5] == "[src/app/api/x.py:2][src/app/api/x.py:9]"

    def test_draws_only_tables_with_or_without_a_catalog(self):
        for ctx in (MAP_CTX, {"extract": MAP_EXTRACT}):
            html = measured.body("interactions.graph", ctx, Refs())

            assert "mermaid-host" not in html and html.count("<table") >= 2

    def test_no_imports_says_so(self):
        assert "No imports between modules were found." in measured.body("interactions.graph", {"extract": {"graph": []}}, Refs())


UI_GRAPH = [
    {"kind": "module", "module": "src/App", "short": "App", "path": "src/App.tsx", "language": "js", "package": None, "is_package": False},
    {"kind": "module", "module": "src/Button", "short": "Button", "path": "src/Button.tsx", "language": "js", "package": None, "is_package": False},
    {"kind": "import", "path": "src/App.tsx", "paths": ["src/Button.tsx"], "from": "src/App", "to": "src/Button", "lines": [1]},
    {"kind": "ui-component", "path": "src/Button.tsx", "line": 3, "name": "Button", "exported": True, "hooks": [], "provides": [], "consumes": []},
    {"kind": "ui-component", "path": "src/App.tsx", "line": 5, "name": "App", "exported": True, "hooks": ["useState", "useAuth"],
     "provides": ["ThemeContext"], "consumes": ["UserContext"]},
    {"kind": "ui-component", "path": "src/App.tsx", "line": 20, "name": "Footer", "exported": False, "hooks": [], "provides": [], "consumes": []},
    {"kind": "renders", "path": "src/App.tsx", "paths": ["src/Button.tsx"], "from": "App", "to": "Button"},
    {"kind": "renders", "path": "src/App.tsx", "paths": ["src/App.tsx"], "from": "App", "to": "Footer"},
]
REACT_ID = "t-interactions-graph-react"


class TestReactTable:
    def html(self, graph=UI_GRAPH, refs=None):
        return measured.body("interactions.graph", {"extract": {"graph": graph}}, refs or Refs())

    def test_one_row_per_component_sorted_by_file_then_name(self):
        rows = rows_of(table_html(self.html(), REACT_ID))

        assert [(r[0], r[1]) for r in rows] == [("App", "src/App.tsx"), ("Footer", "src/App.tsx"), ("Button", "src/Button.tsx")]

    def test_columns_are_those_of_the_plan(self):
        head = re.findall(r"<th(?:\s[^>]*)?>([^<]*)", table_html(self.html(), REACT_ID))

        assert head == ["Component", "File", "Renders", "Rendered by", "Hooks", "Context", "Source"]

    def test_renders_and_rendered_by_come_from_the_renders_items(self):
        rows = {r[0]: r for r in rows_of(table_html(self.html(), REACT_ID))}

        assert rows["App"][2] == "Button, Footer" and rows["App"][3] == "-"
        assert rows["Button"][2] == "-" and rows["Button"][3] == "App"
        assert rows["Footer"][3] == "App"

    def test_hooks_and_context_are_listed(self):
        rows = {r[0]: r for r in rows_of(table_html(self.html(), REACT_ID))}

        assert rows["App"][4] == "useAuth, useState"
        assert rows["App"][5] == "provides ThemeContext; uses UserContext"
        assert rows["Button"][4] == "-" and rows["Button"][5] == "-"

    def test_the_source_column_cites_the_definition_line(self):
        rows = {r[0]: r for r in rows_of(table_html(self.html(refs=MarkedRefs()), REACT_ID))}

        assert rows["Button"][6] == "[src/Button.tsx:3]"

    def test_the_table_follows_the_module_table_under_its_own_heading(self):
        html = self.html()

        assert html.index("Every module import") < html.index("Every React component") < html.index(REACT_ID)

    def test_components_without_any_import_are_still_listed(self):
        graph = [g for g in UI_GRAPH if g["kind"] != "import"]

        html = self.html(graph)

        assert REACT_ID in html and "No imports between modules were found." in html

    def test_a_repository_with_no_components_draws_what_it_drew_before(self):
        html = self.html([g for g in UI_GRAPH if g["kind"] not in ("ui-component", "renders")])

        assert REACT_ID not in html and "React" not in html

    def test_repository_text_is_escaped(self):
        graph = UI_GRAPH + [{"kind": "ui-component", "path": "src/x.tsx", "line": 1, "name": "<b>X</b>", "exported": True, "hooks": [], "provides": [], "consumes": []}]

        assert "<b>X</b>" not in self.html(graph)

    def test_a_tag_named_differently_from_its_definition_is_matched_by_file_when_the_file_has_one_component(self):
        graph = [g for g in UI_GRAPH if g["kind"] != "renders"] + [
            {"kind": "renders", "path": "src/App.tsx", "paths": ["src/Button.tsx"], "from": "App", "to": "Btn"}]

        rows = {r[0]: r for r in rows_of(table_html(self.html(graph), REACT_ID))}

        assert rows["Button"][3] == "App"


API_ITEMS = [
    {"kind": "public-api", "path": "src/store.ts", "line": 4, "name": "create", "symbol_kind": "function", "package": "zustand", "subpath": ".", "audience": "marked private"},
    {"kind": "public-api", "path": "src/vanilla.ts", "line": 9, "name": "createStore", "symbol_kind": "function", "package": "zustand", "subpath": "./vanilla",
     "audience": "marked private"},
    {"kind": "public-api", "path": None, "line": None, "name": "Draft", "symbol_kind": "type", "package": "zustand", "subpath": ".", "audience": "marked private",
     "external": "immer"},
    {"kind": "def", "path": "src/store.ts", "line": 4, "name": "create", "symbol": "x"},
]
API_ID = "t-io-contracts-api"


class TestPublicApi:
    def html(self, items=API_ITEMS, graph=(), refs=None):
        import measured_tables

        return measured_tables.public_api({"extract": {"symbols": list(items), "graph": list(graph)}}, refs or Refs())

    def test_one_row_per_name_by_package_then_import_path_then_name(self):
        rows = rows_of(table_html(self.html(), API_ID))

        assert [(r[0], r[1], r[2]) for r in rows] == [("zustand", "zustand", "Draft"), ("zustand", "zustand", "create"), ("zustand", "zustand/vanilla", "createStore")]

    def test_columns(self):
        head = re.findall(r"<th(?:\s[^>]*)?>([^<]*)", table_html(self.html(), API_ID))

        assert head == ["Package", "Import path", "Name", "Kind", "Defined in", "Audience", "Source"]

    def test_defined_in_names_the_file_or_the_outside_package(self):
        rows = {r[2]: r for r in rows_of(table_html(self.html(), API_ID))}

        assert rows["create"][4] == "src/store.ts" and rows["create"][5] == "marked private"
        assert rows["Draft"][4] == "from immer"

    def test_source_cites_the_defining_line(self):
        rows = {r[2]: r for r in rows_of(table_html(self.html(refs=MarkedRefs()), API_ID))}

        assert rows["createStore"][6] == "[src/vanilla.ts:9]" and rows["Draft"][6] == ""

    def test_the_same_name_twice_is_one_row(self):
        assert len(rows_of(table_html(self.html(API_ITEMS + [API_ITEMS[0]]), API_ID))) == 3

    def test_no_items_in_a_javascript_repository_says_so(self):
        graph = [{"kind": "module", "module": "src/a", "path": "src/a.ts", "language": "js"}]

        assert "No package here declares a public API. What this repository offers from outside is in Entry points." in self.html([], graph)

    def test_no_items_and_no_modules_draws_nothing(self):
        assert self.html([], []) == ""

    def test_repository_text_is_escaped(self):
        item = dict(API_ITEMS[0], name="<i>x</i>")

        assert "<i>x</i>" not in self.html([item])


PY_API = [
    {"kind": "public-api", "path": "src/typedlib/_core.py", "line": 4, "name": "parse", "symbol_kind": "function", "package": "typedlib", "subpath": "typedlib",
     "audience": "listed in __all__, typed", "external": None},
    {"kind": "public-api", "path": "src/typedlib/plugins.py", "line": 8, "name": "Fast", "symbol_kind": "class", "package": "typedlib", "subpath": "typedlib.plugins",
     "audience": "public by name, typed, has a stub", "external": None},
]
PY_MODULE = {"kind": "module", "module": "app.main", "path": "app/main.py", "package": "app", "is_package": False}


class TestPythonPublicApi:
    def html(self, items=PY_API, graph=(PY_MODULE,)):
        import measured_tables

        return measured_tables.public_api({"extract": {"symbols": list(items), "graph": list(graph)}}, Refs())

    def test_the_import_path_is_shown_as_written(self):
        rows = rows_of(table_html(self.html(), API_ID))

        assert [(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows] == [
            ("typedlib", "typedlib", "parse", "function", "src/typedlib/_core.py", "listed in __all__, typed"),
            ("typedlib", "typedlib.plugins", "Fast", "class", "src/typedlib/plugins.py", "public by name, typed, has a stub")]

    def test_a_python_application_with_no_api_says_so(self):
        assert "No package here declares a public API. What this repository offers from outside is in Entry points." in self.html([])

    def test_an_extract_with_no_modules_draws_nothing(self):
        assert self.html([], []) == ""


CS_API = [
    {"kind": "public-api", "path": "src/Lib/Guard.cs", "line": 5, "name": "Guard.Against", "symbol_kind": "property", "package": "Lib", "subpath": "Lib.Guards",
     "audience": "packable"},
    {"kind": "public-api", "path": "src/Lib/Guard.cs", "line": 3, "name": "Guard", "symbol_kind": "class", "package": "Lib", "subpath": "Lib.Guards", "audience": "packable"},
    {"kind": "public-api", "path": "src/Lib/Root.cs", "line": 2, "name": "Root", "symbol_kind": "class", "package": "Lib", "subpath": "", "audience": "packable, obsolete"},
]
CS_GRAPH = [{"kind": "module", "module": "src/Lib/Guard", "path": "src/Lib/Guard.cs", "language": "csharp"},
            {"kind": "cs-project", "path": "src/Lib/Lib.csproj", "name": "Lib", "packable": True, "friends": ["Lib.Tests", "Lib.Bench"]},
            {"kind": "cs-project", "path": "src/Web/Web.csproj", "name": "Web", "packable": False, "friends": ["Web.Tests"]}]


class TestCSharpPublicApi:
    def html(self, items=CS_API, graph=CS_GRAPH):
        import measured_tables

        return measured_tables.public_api({"extract": {"symbols": list(items), "graph": list(graph)}}, Refs())

    def test_rows_are_ordered_by_package_namespace_and_name_with_the_namespace_as_import_path(self):
        rows = rows_of(table_html(self.html(), API_ID))

        assert [(r[0], r[1], r[2]) for r in rows] == [("Lib", "Lib", "Root"), ("Lib", "Lib.Guards", "Guard"), ("Lib", "Lib.Guards", "Guard.Against")]
        assert rows[0][5] == "packable, obsolete"

    def test_a_friend_line_follows_the_table_for_each_packable_project_and_friend(self):
        html = self.html()
        lines = re.findall(r'<p class="muted">([^<]*)</p>', html.split("</table>")[-1])

        assert lines == ["Lib lets Lib.Bench use its internal names (InternalsVisibleTo).", "Lib lets Lib.Tests use its internal names (InternalsVisibleTo)."]

    def test_friend_lines_for_a_project_that_is_not_packable_are_left_out(self):
        assert "Web.Tests" not in self.html()

    def test_a_csharp_repository_with_no_packable_project_says_no_package_declares_an_api(self):
        graph = [dict(g, packable=False) if g["kind"] == "cs-project" else g for g in CS_GRAPH]

        assert "No package here declares a public API." in self.html([], graph)

    def test_a_repository_with_no_modules_draws_nothing(self):
        assert self.html([], []) == ""


class TestJavaScriptAreas:
    EXTRACT = {"graph": [{"kind": "source-root", "path": "apps/react-vite/package.json", "root": "apps"},
                         {"kind": "source-root", "path": "apps/nextjs/package.json", "root": "apps"},
                         {"kind": "source-root", "path": "package.json", "root": ""}]}

    def test_package_roots_include_the_source_roots(self):
        assert measured_graph.package_roots(self.EXTRACT) == ["apps"]

    def test_each_app_is_an_area_below_the_apps_folder(self):
        roots = measured_graph.package_roots(self.EXTRACT)

        assert measured_graph.component_area(["apps/react-vite/src/"], roots) == "react-vite"

    def test_python_roots_are_unchanged(self):
        extract = {"graph": [{"kind": "module", "path": "src/cannalerts/__init__.py", "module": "cannalerts", "package": "cannalerts", "is_package": True}]}

        assert measured_graph.package_roots(extract) == ["src/cannalerts"]


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
