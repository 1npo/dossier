import json
import re
from pathlib import Path

import js_reduce
import scip_read
import pytest

CRUISE = json.loads((Path(__file__).parents[2] / "fixtures" / "js_tools" / "depcruise.json").read_text())
TEST_RE = re.compile(r"\.(test|spec)\.[jt]sx?$")
FILES = ["src/a.ts", "src/b.ts", "src/c.ts", "src/d.ts", "src/lazy.ts", "src/barrel/index.ts", "src/auth.ts", "src/auth.tsx", "src/a.test.ts", "src/types.d.ts"]
PROJECT = {"dir": "", "files": FILES}
TREE = frozenset(FILES)


@pytest.fixture(name="graph")
def graph_fixture():
    return js_reduce.graph_items(CRUISE, PROJECT, TREE, [{"path": "src/a.ts", "specifier": "./b", "line": 3}], TEST_RE)


class TestModuleName:
    def test_extension_is_dropped(self):
        assert js_reduce.module_name("src/a.ts", ["src/a.ts", "src/b.ts"]) == "src/a"

    def test_same_stem_in_a_folder_keeps_the_full_path(self):
        assert js_reduce.module_name("src/auth.ts", ["src/auth.ts", "src/auth.tsx"]) == "src/auth.ts"


class TestShortName:
    def test_index_file_uses_the_folder_name(self):
        assert js_reduce.short_name("src/barrel/index.ts") == "barrel"

    def test_plain_file_uses_its_stem(self):
        assert js_reduce.short_name("src/users/service.ts") == "service"


class TestGraphItems:
    def test_modules_exclude_tests_and_declaration_files(self, graph):
        items, _ = graph

        modules = {i["path"] for i in items if i["kind"] == "module"}

        assert "src/a.test.ts" not in modules and "src/types.d.ts" not in modules and len(modules) == 8
        assert next(i for i in items if i["path"] == "src/barrel/index.ts")["short"] == "barrel"

    def test_edges_to_packages_core_modules_and_declarations_are_dropped(self, graph):
        items, _ = graph

        edges = {(i["from"], i["to"]) for i in items if i["kind"] == "import"}

        assert edges == {("src/a", "src/b"), ("src/b", "src/a"), ("src/c", "src/d"), ("src/d", "src/c"), ("src/lazy", "src/a")}

    def test_edges_from_test_files_go_to_test_edges(self, graph):
        _, test_edges = graph

        assert test_edges == [("src/a.test.ts", "src/a.ts")]

    def test_lines_are_joined_by_file_and_specifier(self, graph):
        items, _ = graph

        edge = next(i for i in items if i["kind"] == "import" and i["from"] == "src/a")

        assert edge["lines"] == [3] and edge["via"] == "dependency-cruiser"

    def test_type_only_and_dynamic_flags_follow_the_tool(self, graph):
        items, _ = graph

        flags = {i["from"]: (i["type_only"], i["dynamic"]) for i in items if i["kind"] == "import"}

        assert flags["src/c"] == (True, False) and flags["src/lazy"] == (False, True) and flags["src/a"] == (False, False)

    def test_cycle_counts_run_time_imports_only(self, graph):
        items, _ = graph

        cycles = [i["modules"] for i in items if i["kind"] == "cycle"]

        assert cycles == [["src/a", "src/b"]]

    def test_project_folder_prefixes_every_path(self):
        cruise = {"modules": [{"source": "src/x.ts", "dependencies": [{"module": "./y", "resolved": "src/y.ts", "dependencyTypes": ["local"], "dynamic": False}]}]}
        tree = frozenset({"apps/w/src/x.ts", "apps/w/src/y.ts"})

        items, _ = js_reduce.graph_items(cruise, {"dir": "apps/w", "files": sorted(tree)}, tree, [], TEST_RE)

        assert next(i for i in items if i["kind"] == "import")["paths"] == ["apps/w/src/y.ts"]


class TestContractItems:
    VIOLATION = {"from": "src/users/service.ts", "to": "src/main.ts", "rule": {"name": "no-up", "severity": "error"}}

    def test_a_violated_rule_is_broken_with_its_edge(self):
        items = js_reduce.contract_items([self.VIOLATION], ["no-up"], ".dependency-cruiser.json", {"src/users/service.ts": "src/users/service"},
                                         {("src/users/service.ts", "src/main.ts"): 2})

        assert items[0]["status"] == "broken" and items[0]["violations"] == [
            {"from": "src/users/service", "to": "src/main.ts", "path": "src/users/service.ts", "line": 2}]

    def test_a_rule_without_violations_is_kept(self):
        items = js_reduce.contract_items([], ["no-up"], ".dependency-cruiser.json")

        assert (items[0]["status"], items[0]["violations"], items[0]["reason"]) == ("kept", [], None)


KNIP = json.loads((Path(__file__).parents[2] / "fixtures" / "js_tools" / "knip.json").read_text())


class TestDeadItems:
    def test_unused_file_export_type_and_dependency_are_reported_with_prefixed_paths(self):
        items = js_reduce.dead_items(KNIP, {"dir": "apps/w"})

        by_type = {i["type"]: i for i in items}
        assert by_type["unused file"]["path"] == "apps/w/src/unused.ts"
        assert (by_type["unused export"]["path"], by_type["unused export"]["name"], by_type["unused export"]["line"]) == ("apps/w/src/a.ts", "extra", 4)
        assert by_type["unused type"]["name"] == "Local"
        assert by_type["unused dependency"]["path"] == "apps/w/package.json" and by_type["unused dependency"]["name"] == "left-pad"

    def test_items_carry_the_fields_the_dead_card_reads(self):
        items = js_reduce.dead_items(KNIP, {"dir": ""})

        for i in items:
            assert i["confidence"] is None and i["rule"].startswith("knip.") and i["snippet"] == i["name"] and i["message"]

    def test_an_empty_report_gives_no_items(self):
        assert js_reduce.dead_items({"issues": []}, {"dir": ""}) == []


def _index(path, symbol, role, rng=(0, 0, 0, 1)):
    return {"path": path, "occurrences": [{"range": list(rng), "symbol": symbol, "roles": role, "enclosing_range": None}],
            "symbols": [{"symbol": symbol, "display_name": symbol.rsplit("/", 1)[-1].strip("."), "documentation": []}]}


class TestJoinIndexes:
    def test_document_paths_get_the_project_folder_and_references_cross_projects(self):
        lib = "scip-typescript npm lib 1.0.0 `src/x.ts`/f()."
        a = {"documents": [_index("src/x.ts", lib, 1)]}
        b = {"documents": [_index("src/y.ts", lib, 0)]}

        items = scip_reduce(js_reduce.join_indexes([("pkg/lib", a), ("apps/web", b)]))

        assert [i["path"] for i in items if i["kind"] == "def"] == ["pkg/lib/src/x.ts"]
        assert [(i["path"], i["paths"]) for i in items if i["kind"] == "ref-edge"] == [("apps/web/src/y.ts", ["pkg/lib/src/x.ts"])]


def scip_reduce(index):
    return scip_read.reduce(index)


class TestFinishSymbols:
    DEFS = [{"kind": "def", "path": "src/a.ts", "name": "a", "symbol": "scip-typescript npm tiny 1.0.0 `src/a.ts`/a.", "public": True},
            {"kind": "def", "path": "src/a.ts", "name": "hidden", "symbol": "scip-typescript npm tiny 1.0.0 `src/a.ts`/hidden().", "public": True},
            {"kind": "def", "path": "src/a.ts", "name": "run", "symbol": "scip-typescript npm tiny 1.0.0 `src/a.ts`/Svc#run().", "public": True},
            {"kind": "ref-edge", "path": "src/b.ts", "paths": ["src/a.ts"], "count": 1}]

    def test_public_follows_the_exports_of_the_file(self):
        out = js_reduce.finish_symbols(self.DEFS, [{"path": "src/a.ts", "name": "a"}])

        assert [(d["name"], d["public"]) for d in out if d["kind"] == "def"] == [("a", True), ("hidden", False), ("run", False)]

    def test_a_member_of_an_exported_class_is_public(self):
        out = js_reduce.finish_symbols(self.DEFS, [{"path": "src/a.ts", "name": "Svc"}])

        assert next(d for d in out if d["name"] == "run")["public"] is True

    def test_a_renamed_export_makes_the_local_name_public(self):
        out = js_reduce.finish_symbols(self.DEFS, [{"path": "src/a.ts", "name": "alias", "local": "hidden"}])

        assert next(d for d in out if d["name"] == "hidden")["public"] is True

    def test_without_exports_the_reducer_value_is_kept(self):
        out = js_reduce.finish_symbols(self.DEFS, None)

        assert all(d["public"] for d in out if d["kind"] == "def")

    def test_symbols_lose_package_and_version(self):
        out = js_reduce.finish_symbols(self.DEFS, None)

        assert out[0]["symbol"] == "scip-typescript npm . . `src/a.ts`/a." and out[3] == self.DEFS[3]


class TestFinishSymbolsNestedFiles:
    def test_a_file_below_a_folder_uses_the_name_after_the_file(self):
        defs = [{"kind": "def", "path": "src/types.ts", "name": "Order", "symbol": "scip-typescript npm shopjs 1.0.0 src/`types.ts`/Order#", "public": True},
                {"kind": "def", "path": "src/types.ts", "name": "note", "symbol": "scip-typescript npm shopjs 1.0.0 src/`types.ts`/Order#note.", "public": True},
                {"kind": "def", "path": "src/types.ts", "name": "Local", "symbol": "scip-typescript npm shopjs 1.0.0 src/`types.ts`/Local#", "public": True}]

        out = js_reduce.finish_symbols(defs, [{"path": "src/types.ts", "name": "Order"}])

        assert [(d["name"], d["public"]) for d in out] == [("Order", True), ("note", True), ("Local", False)]


def _type(name, kind="interface", **kw):
    return {"path": "src/types.ts", "name": name, "kind": kind, "line": 1, "end_line": 3, "exported": True, "object": kind == "interface",
            "bases": [], "decorators": [], "fields": kw.pop("fields", []), **kw}


class TestModelItems:
    def test_exported_interfaces_object_types_enums_and_entity_classes_are_kept(self):
        types = [_type("Order"), _type("Item", "type", object=True), _type("Status", "enum"), _type("Product", "class", decorators=["Entity"])]

        items = js_reduce.model_items(types)

        assert {(i["name"], i["kind"]) for i in items} == {("Order", "ts-interface"), ("Item", "ts-type"), ("Status", "ts-enum"), ("Product", "typeorm")}

    def test_props_local_tests_declarations_and_stories_are_dropped(self):
        types = [_type("ButtonProps"), _type("Local", exported=False), {**_type("T"), "path": "src/a.test.ts"}, {**_type("D"), "path": "src/x.d.ts"},
                 {**_type("S"), "path": "src/B.stories.tsx"}, _type("Svc", "class"), _type("Alias", "type", object=False)]

        assert js_reduce.model_items(types) == []

    def test_a_field_whose_type_names_another_entity_has_a_ref(self):
        types = [_type("Order", fields=[{"name": "buyer", "type": "User[]", "line": 2, "optional": False}]), _type("User")]

        items = {i["name"]: i for i in js_reduce.model_items(types)}

        assert items["Order"]["fields"][0]["ref"] == "User"
