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


class TestEntriesOnTheFixture:
    @pytest.fixture
    def found(self, decls, cs_repo):
        import cs_entries
        import cs_project
        files = sorted(str(p.relative_to(cs_repo.path)) for p in Path(cs_repo.path).rglob("*") if p.is_file() and ".git/" not in str(p))
        result = cs_project.projects(files, lambda f: (Path(cs_repo.path) / f).read_text(encoding="utf-8", errors="replace"))
        rows = (cs_entries.controller_routes(decls) + cs_entries.program_entries(result, decls) + cs_entries.class_entries(decls)
                + cs_entries.function_entries(decls) + cs_entries.page_routes(files, lambda f: (Path(cs_repo.path) / f).read_text(encoding="utf-8", errors="replace")))
        return {(r["kind"], r["name"]): r for r in rows}

    def test_the_controller_routes_sit_on_their_marker_lines(self, found, cs_repo):
        path = "src/Shop.Api/Controllers/OrdersController.cs"

        assert found[("http-route", "GET /api/Orders")]["line"] == cs_repo.line_of(path, "ep-ctl-list")
        assert ("http-route", "GET /api/Orders/{id}") in found and ("http-route", "POST /submit") in found

    def test_the_other_kinds_are_found(self, found):
        assert ("program-main", "Shop.Api") in found and ("program-main", "Legacy") in found and ("hosted-service", "Cleanup") in found
        assert ("queue-consumer", "MailConsumer") in found and ("function", "Ping") in found and ("scheduled-job", "Tick") in found
        assert ("ui-route", "/counter") in found

    def test_conventional_controllers_give_nothing(self, found):
        assert not [k for k in found if k[1].startswith("GET /Home")]


class TestModelsOnTheFixture:
    def test_order_and_customer_are_entities_and_the_dto_is_not(self, decls, cs_repo):
        import cs_models
        root = Path(cs_repo.path)
        rows = cs_models.model_items(decls, {"projects": []}, lambda f: (root / f).read_text(encoding="utf-8", errors="replace"))
        got = {(r["kind"], r["name"]): r for r in rows}

        assert ("ef-entity", "Order") in got and ("ef-entity", "Customer") in got and ("cs-enum", "OrderStatus") in got
        assert not [k for k in got if k[1] == "OrderDto"]
        assert got[("ef-entity", "Order")]["line"] == cs_repo.line_of("src/Shop.Core/Order.cs", "model-order")
        assert sorted(r["name"] for r in rows if r["kind"] == "migration") == ["20260101000000_Init", "ShopContextModelSnapshot"]
        assert [f["many"] for f in got[("ef-entity", "Customer")]["fields"] if f["name"] == "Orders"] == [True]
