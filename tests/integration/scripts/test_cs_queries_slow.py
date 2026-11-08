import functools
import os
from pathlib import Path

import pytest

import cs_queries
import sandbox
import shared_tools

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")


@pytest.fixture
def ts(tmp_path, cs_repo):
    area = tmp_path / "cache" / "repo"
    area.mkdir(parents=True)
    return shared_tools.TreeSitter(functools.partial(sandbox.run, area=area, cwd=Path(cs_repo.path), timeout=600))


@pytest.fixture
def decls(ts, cs_repo):
    files = sorted(str(p.relative_to(cs_repo.path)) for p in Path(cs_repo.path).rglob("*.cs"))
    return cs_queries.declarations(ts, files)


def _type(decls, path, name):
    return next(t for t in decls[path]["types"] if t["name"] == name)


class TestDeclarationsOnTheFixture:
    def test_the_controller_has_its_class_and_method_attributes(self, decls):
        path = "src/Shop.Api/Controllers/OrdersController.cs"

        t = _type(decls, path, "OrdersController")
        get = next(m for m in t["members"] if m["name"] == "Get")

        assert [a["name"] for a in t["attributes"]] == ["ApiController", "Route"]
        assert t["bases"] == ["ControllerBase"] and t["namespace"] == "Shop.Api.Controllers"
        assert [(a["name"], a["args"]) for a in get["attributes"]] == [("HttpGet", '"{id}"')]
        assert [p["name"] for p in get["params"]] == ["id", "tenant"]

    def test_totals_is_partial_in_two_files(self, decls):
        a = _type(decls, "src/Shop.Core/Totals.A.cs", "Totals")
        b = _type(decls, "src/Shop.Core/Totals.B.cs", "Totals")

        assert a["partial"] and b["partial"]

    def test_program_has_top_level_statements(self, decls):
        assert decls["src/Shop.Api/Program.cs"]["top_level"] is True
        assert decls["src/Shop.Core/Totals.A.cs"]["top_level"] is False

    def test_a_nested_type_names_its_outer_type(self, decls):
        inner = _type(decls, "src/Shop.Core/Outer.cs", "Inner")
        outer = _type(decls, "src/Shop.Core/Outer.cs", "Outer")

        assert inner["outer"] == "Outer"
        assert {m["name"]: m["modifiers"] for m in outer["members"]} == {"P": ["protected"], "Q": ["private"]}

    def test_a_namespace_inside_an_if_block_is_read(self, decls):
        assert [n["name"] for n in decls["src/Shop.Core/Polyfill.cs"]["namespaces"]] == ["System.Runtime.CompilerServices"]

    def test_every_file_asked_for_has_an_entry(self, decls):
        assert all(isinstance(v, dict) and "types" in v for v in decls.values()) and len(decls) > 30


class TestComplexityOnTheFixture:
    def test_a_file_with_branches_has_a_number_and_a_plain_one_has_zero(self, ts):
        got = cs_queries.complexity(ts, ["src/Shop.Api/Services/OrderService.cs", "src/Shop.Core/Totals.A.cs"])

        assert got["src/Shop.Api/Services/OrderService.cs"] > 0 and got["src/Shop.Core/Totals.A.cs"] == 0
