import json
import re
from pathlib import Path

import js_reduce
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
