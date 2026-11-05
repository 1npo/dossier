import functools
import os
from pathlib import Path

import pytest

import py_queries
import sandbox
import shared_tools

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")

MODULE_PATHS = {"shopcart": "src/shopcart/__init__.py", "shopcart.core": "src/shopcart/core.py",
                "shopcart.cli": "src/shopcart/cli.py", "shopcart.store": "src/shopcart/store.py"}
SRC = ["src/shopcart/models.py", "src/shopcart/core.py", "src/shopcart/plugins.py", "src/shopcart/store.py",
       "src/shopcart/cli.py", "src/shopcart/__init__.py"]


@pytest.fixture
def ts(tmp_path, py_repo):
    area = tmp_path / "cache" / "repo"
    area.mkdir(parents=True)
    return shared_tools.TreeSitter(functools.partial(sandbox.run, area=area, cwd=Path(py_repo.path), timeout=600))


class TestModelsOnTheFixture:
    def test_models_are_exactly_item_status_and_order(self, ts):
        got = py_queries.models(ts, SRC)

        assert [(m["name"], m["kind"]) for m in got] == [("Item", "dataclass"), ("Status", "enum"), ("Order", "pydantic")]

    def test_models_are_at_their_marker_lines(self, ts, py_repo):
        got = {m["name"]: m for m in py_queries.models(ts, SRC)}

        assert got["Item"]["line"] == py_repo.line_of("src/shopcart/models.py", "model-item")
        assert got["Order"]["line"] == py_repo.line_of("src/shopcart/models.py", "model-order")

    def test_fields_and_refs(self, ts, py_repo):
        got = {m["name"]: m for m in py_queries.models(ts, SRC)}

        assert [f["name"] for f in got["Item"]["fields"]] == ["sku", "price"]
        assert [f["name"] for f in got["Status"]["fields"]] == ["OPEN"]
        assert {f["name"]: f["ref"] for f in got["Order"]["fields"]} == {"items": "Item", "status": "Status"}
        assert got["Order"]["fields"][0]["line"] == py_repo.line_of("src/shopcart/models.py", "field-items")


class TestTestsOnTheFixture:
    def test_test_file_counts_and_source_paths(self, ts):
        got = py_queries.tests(ts, ["tests/test_core.py"], MODULE_PATHS)

        assert len(got) == 1
        item = got[0]
        assert (item["path"], item["tests"], item["skips"], item["fixtures"], item["framework"]) == ("tests/test_core.py", 3, 1, 1, "pytest")
        assert item["mocks"] >= 1 and "src/shopcart/core.py" in item["paths"]


class TestModuleStateOnTheFixture:
    def test_mutable_module_values_only(self, ts, py_repo):
        got = {i["name"]: i for i in py_queries.module_state(ts, SRC)}

        assert set(got) == {"CART", "REGISTRY"}
        assert got["CART"]["line"] == py_repo.line_of("src/shopcart/core.py", "state-module")
        assert got["REGISTRY"]["line"] == py_repo.line_of("src/shopcart/plugins.py", "state-registry")


class TestImportsOnTheFixture:
    def test_import_edges_of_cli(self, ts):
        got = py_queries.imports(ts, ["src/shopcart/cli.py"], MODULE_PATHS)

        assert {(i["from"], i["to"]) for i in got} == {("shopcart.cli", "shopcart.core"), ("shopcart.cli", "shopcart.store")}


class TestComplexityOnTheFixture:
    def test_every_branch_node_name_exists_in_the_pinned_grammar(self, ts, tmp_path):
        (tmp_path / "w").mkdir()
        sample = ("def f(x, y):\n    if x:\n        pass\n    elif y:\n        pass\n    for i in x:\n        pass\n    while y:\n        break\n"
                  "    try:\n        pass\n    except ValueError:\n        pass\n    z = 1 if x else 2\n    w = x and y\n"
                  "    match x:\n        case 1:\n            pass\n")
        (tmp_path / "w" / "branches.py").write_text(sample)
        ts_here = shared_tools.TreeSitter(functools.partial(sandbox.run, area=tmp_path / "cache" / "repo", cwd=tmp_path / "w", timeout=600))

        got = py_queries.complexity(ts_here, ["branches.py"])

        assert got == {"branches.py": 8}

    def test_fixture_files_each_get_a_number(self, ts):
        got = py_queries.complexity(ts, SRC)

        assert set(got) == set(SRC) and got["src/shopcart/core.py"] > 0
