import py_queries


def cap(capture, text, line, col=0, end_line=None, path="m.py"):
    return {"path": path, "capture": capture, "start_line": line, "start_col": col, "end_line": end_line or line,
            "end_col": col + len(text), "text": text}


class FakeTS:
    def __init__(self, by_query):
        self.by_query, self.calls = by_query, []

    def query(self, language, paths, query):
        self.calls.append((language, paths, query))
        return self.by_query.get(query, [])


def model_inputs():
    classes = [cap("class", "class Item:\n    sku: str", 6, end_line=8), cap("class.name", "Item", 6, 6),
               cap("class.body", "sku: str", 7, 4, end_line=8),
               cap("class", "class Status(Enum):\n    OPEN = 1", 11, end_line=12), cap("class.name", "Status", 11, 6),
               cap("class.bases", "(Enum)", 11, 12), cap("class.body", "OPEN = 1", 12, 4),
               cap("class", "class Order(BaseModel):\n    items: list[Item]", 15, end_line=17), cap("class.name", "Order", 15, 6),
               cap("class.bases", "(BaseModel)", 15, 11), cap("class.body", "items: list[Item]", 16, 4, end_line=17),
               cap("class", "class Plain:\n    x = 1", 20, end_line=21), cap("class.name", "Plain", 20, 6),
               cap("class.body", "x = 1", 21, 4)]
    fields = [cap("field.name", "sku", 7, 4), cap("field.type", "str", 7, 9),
              cap("field.name", "price", 8, 4), cap("field.type", "float", 8, 11),
              cap("field.name", "OPEN", 12, 4), cap("field.value", "1", 12, 11),
              cap("field.name", "items", 16, 4), cap("field.type", "list[Item]", 16, 11),
              cap("field.name", "status", 17, 4), cap("field.type", "Status", 17, 12),
              cap("field.name", "x", 21, 4), cap("field.value", "1", 21, 8)]
    decorated = [cap("decorated", "@dataclass\nclass Item:\n    sku: str", 5, end_line=8)]
    return classes, fields, decorated


class TestSplitBases:
    def test_top_level_commas_split_and_keywords_are_dropped(self):
        assert py_queries.split_bases("(Base, mixins.A, Generic[T, U], metaclass=Meta)") == ["Base", "mixins.A", "Generic[T, U]"]

    def test_empty_parentheses_give_no_bases(self):
        assert py_queries.split_bases("()") == []


class TestAssembleModels:
    def test_each_model_kind_comes_from_bases_or_decorators(self):
        got = py_queries.assemble_models(*model_inputs())

        assert [(m["name"], m["kind"]) for m in got] == [("Item", "dataclass"), ("Status", "enum"), ("Order", "pydantic")]

    def test_plain_class_is_not_a_model(self):
        got = py_queries.assemble_models(*model_inputs())

        assert "Plain" not in {m["name"] for m in got}

    def test_dataclass_fields_have_types_and_lines(self):
        item = py_queries.assemble_models(*model_inputs())[0]

        assert [(f["name"], f["type"], f["line"]) for f in item["fields"]] == [("sku", "str", 7), ("price", "float", 8)]
        assert item["line"] == 6 and item["snippet"] == "class Item:" and item["rule"] == "dataclass"

    def test_enum_fields_are_plain_assignments(self):
        status = py_queries.assemble_models(*model_inputs())[1]

        assert [f["name"] for f in status["fields"]] == ["OPEN"] and status["fields"][0]["type"] is None

    def test_field_naming_another_model_gets_a_ref(self):
        order = py_queries.assemble_models(*model_inputs())[2]

        assert {f["name"]: f["ref"] for f in order["fields"]} == {"items": "Item", "status": "Status"}

    def test_foreign_key_value_gives_a_ref(self):
        classes = [cap("class", "class Line(Base):\n    ...", 1, end_line=3), cap("class.name", "Line", 1, 6),
                   cap("class.bases", "(Base)", 1, 10), cap("class.body", "...", 2, 4, end_line=3)]
        fields = [cap("field.name", "order_id", 2, 4), cap("field.value", "Column(ForeignKey('orders.id'))", 2, 15)]

        got = py_queries.assemble_models(classes, fields, [])

        assert got[0]["kind"] == "sqlalchemy" and got[0]["fields"][0]["ref"] == "orders"

    def test_subclass_of_a_model_is_a_model_of_the_same_kind(self):
        classes = [cap("class", "class A(BaseModel):\n    ...", 1, end_line=2), cap("class.name", "A", 1, 6), cap("class.bases", "(BaseModel)", 1, 7),
                   cap("class.body", "...", 2, 4), cap("class", "class B(A):\n    ...", 4, end_line=5), cap("class.name", "B", 4, 6),
                   cap("class.bases", "(A)", 4, 7), cap("class.body", "...", 5, 4)]

        got = py_queries.assemble_models(classes, [], [])

        assert [(m["name"], m["kind"]) for m in got] == [("A", "pydantic"), ("B", "pydantic")]

    def test_nested_class_fields_belong_to_the_inner_class(self):
        classes = [cap("class", "class Outer(BaseModel):\n ...", 1, end_line=8), cap("class.name", "Outer", 1, 6),
                   cap("class.bases", "(BaseModel)", 1, 11), cap("class.body", "class Inner...", 3, 4, end_line=8),
                   cap("class", "class Inner(BaseModel):\n ...", 3, 4, end_line=5), cap("class.name", "Inner", 3, 10),
                   cap("class.bases", "(BaseModel)", 3, 15), cap("class.body", "a: int", 4, 8, end_line=5)]
        fields = [cap("field.name", "a", 4, 8), cap("field.type", "int", 4, 11), cap("field.name", "b", 7, 4), cap("field.type", "int", 7, 7)]

        got = {m["name"]: [f["name"] for f in m["fields"]] for m in py_queries.assemble_models(classes, fields, [])}

        assert got == {"Outer": ["b"], "Inner": ["a"]}


class TestMigrations:
    def test_alembic_and_django_migrations_come_from_paths(self):
        got = py_queries.migrations(["alembic/versions/001_x.py", "app/migrations/0002_y.py", "app/migrations/__init__.py", "app/models.py"])

        assert [(m["path"], m["tool"]) for m in got] == [("alembic/versions/001_x.py", "alembic"), ("app/migrations/0002_y.py", "django")]


class TestAssembleState:
    def test_mutable_module_values_become_candidates(self):
        matches = [cap("state.name", "registry", 4, 0), cap("state.value", "[1,\n 2]", 4, 11, end_line=5)]

        got = py_queries.assemble_state(matches)

        assert [(i["name"], i["line"], i["end_line"]) for i in got] == [("registry", 4, 5)]
        assert got[0]["rule"] == "dossier.python.state.module-mutable" and got[0]["category"] == "global-state"

    def test_all_capitals_name_with_a_filled_value_is_a_constant(self):
        assert py_queries.assemble_state([cap("state.name", "LIMITS", 3, 0), cap("state.value", '{"a": 1}', 3, 9)]) == []

    def test_all_capitals_name_with_an_empty_container_is_state(self):
        got = py_queries.assemble_state([cap("state.name", "CART", 3, 0), cap("state.value", "{}", 3, 7)])

        assert [i["name"] for i in got] == ["CART"]


class TestParseImport:
    def test_plain_import_lists_every_module(self):
        assert py_queries.parse_import("import a.b as c, d", "x") == [("a.b", []), ("d", [])]

    def test_from_import_lists_names_across_lines(self):
        assert py_queries.parse_import("from a import (\n    b,\n    c as d,\n)", "x") == [("a", ["b", "c"])]

    def test_relative_import_in_a_module_resolves_against_its_package(self):
        assert py_queries.parse_import("from . import util", "pkg.sub.mod") == [("pkg.sub", ["util"])]

    def test_two_dots_go_one_package_up(self):
        assert py_queries.parse_import("from ..core import x", "pkg.sub.mod") == [("pkg.core", ["x"])]

    def test_relative_import_in_a_package_init_starts_at_the_package(self):
        assert py_queries.parse_import("from .a import x", "pkg.sub", is_package=True) == [("pkg.sub.a", ["x"])]


class TestResolve:
    PATHS = {"shopcart": "src/shopcart/__init__.py", "shopcart.core": "src/shopcart/core.py"}

    def test_from_import_of_a_submodule_gives_the_submodule(self):
        assert py_queries.resolve([("shopcart", ["core"])], self.PATHS) == ["shopcart.core"]

    def test_from_import_of_a_name_gives_the_module(self):
        assert py_queries.resolve([("shopcart.core", ["total"])], self.PATHS) == ["shopcart.core"]

    def test_longest_known_prefix_wins_for_a_plain_import(self):
        assert py_queries.resolve([("shopcart.core.x", [])], self.PATHS) == ["shopcart.core"]

    def test_unknown_module_gives_nothing(self):
        assert py_queries.resolve([("requests", [])], self.PATHS) == []


class TestAssembleImports:
    def test_import_edges_carry_lines_and_files(self):
        paths = {"tool": "tool.py", "helper": "helper.py"}
        matches = [cap("import.stmt", "import helper", 1, path="tool.py"), cap("import.from", "from helper import x", 4, path="tool.py"),
                   cap("import.stmt", "import os", 2, path="tool.py")]

        got = py_queries.assemble_imports(matches, paths)

        assert got == [{"kind": "import", "path": "tool.py", "paths": ["helper.py"], "from": "tool", "to": "helper", "lines": [1, 4],
                        "via": "tree-sitter"}]


class TestAssembleTests:
    PATHS = {"shopcart.core": "src/shopcart/core.py", "shopcart": "src/shopcart/__init__.py"}

    def matches(self):
        return {"tests/integration/test_core.py": [
            cap("func.name", "test_a", 5), cap("func.name", "test_b", 9), cap("func.name", "helper", 12),
            cap("class.name", "TestThing", 15), cap("class.name", "Helper", 30),
            cap("decorator", "@pytest.mark.skip(reason='x')", 8), cap("decorator", "@pytest.mark.xfail", 11),
            cap("decorator", "@pytest.fixture", 3), cap("call.fn", "mock.patch", 6), cap("call.fn", "print", 7),
            cap("call.fn", "monkeypatch.setattr", 10), cap("import.from", "from shopcart import core", 1)]}

    def test_counts_and_kind(self):
        item = py_queries.assemble_tests(self.matches(), self.PATHS)[0]

        assert (item["tests"], item["classes"], item["skips"], item["xfails"], item["fixtures"], item["mocks"]) == (2, 1, 1, 1, 1, 2)
        assert (item["test_kind"], item["framework"]) == ("integration", "pytest")

    def test_imports_resolve_to_project_modules_and_files(self):
        item = py_queries.assemble_tests(self.matches(), self.PATHS)[0]

        assert item["imports"] == ["shopcart.core"] and item["paths"] == ["src/shopcart/core.py"]

    def test_testcase_base_makes_it_unittest(self):
        got = py_queries.assemble_tests({"tests/test_x.py": [cap("class.bases", "(unittest.TestCase)", 3)]}, {})

        assert got[0]["framework"] == "unittest" and got[0]["test_kind"] == "unit"

    def test_e2e_folder_is_e2e(self):
        assert py_queries.assemble_tests({"tests/e2e/test_x.py": []}, {})[0]["test_kind"] == "e2e"


class TestDrivers:
    def test_models_runs_three_queries_and_adds_migrations(self):
        ts = FakeTS({})

        got = py_queries.models(ts, ["app/migrations/0001_a.py"])

        assert [q for _, _, q in ts.calls] == [py_queries.CLASS_Q, py_queries.FIELD_Q, py_queries.DECORATOR_Q]
        assert got[0]["kind"] == "migration"

    def test_no_files_run_no_queries(self):
        ts = FakeTS({})

        assert (py_queries.models(ts, []), py_queries.module_state(ts, []), py_queries.imports(ts, [], {}), py_queries.tests(ts, [], {})) == ([], [], [], [])
        assert ts.calls == []
