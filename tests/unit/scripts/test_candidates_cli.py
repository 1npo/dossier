import pytest

import candidates
from components import component_of, parse_paths


def io(path, line, category, rule, snippet):
    return {"path": path, "line": line, "end_line": line, "category": category, "rule": rule, "snippet": snippet}


def build_extract():
    ios = candidates.assign_ids("io_candidates", [
        io("a.py", 3, "env-var", "dossier.python.input.env-var", 'os.getenv("A")'),
        io("a.py", 9, "env-var", "dossier.python.input.env-var", 'os.getenv("B")'),
        io("a.py", 12, "stdout", "dossier.python.output.stdout", 'print("x")'),
        io("b.py", 2, "stdout", "dossier.python.output.stdout", 'print("y")')])
    eps = candidates.assign_ids("entry_points", [{"path": "cli.py", "line": 5, "end_line": 8, "kind": "main-guard", "name": "__main__",
                                                  "rule": "dossier.python.entry.main-guard", "snippet": 'if __name__ == "__main__":'}])
    models = candidates.assign_ids("models", [{"path": "m.py", "line": 1, "end_line": 4, "name": "Item", "kind": "dataclass", "rule": "dataclass",
                                               "snippet": "class Item:"}, {"path": "mig/0001.py", "kind": "migration", "tool": "django"}])
    return {"io_candidates": ios, "entry_points": eps, "models": models}


def ids_where(extract, **match):
    return [i["id"] for i in extract["io_candidates"] if all(i.get(k) == v for k, v in match.items())]


def reports_for(extract):
    env_a = ids_where(extract, snippet='os.getenv("A")')[0]
    stdout_group = next(i["group"] for i in extract["io_candidates"] if i["path"] == "a.py" and i["category"] == "stdout")
    return {"io": {"cards": [{"card": "io.inputs", "blocks": [{"type": "table", "rows": [{"cells": ["x"], "cand": [env_a]}]}],
                              "dismissed": [{"cand": [stdout_group], "reason": "Debug output."}]}]}}


class TestHomeCard:
    @pytest.mark.parametrize("category,card", sorted(candidates.CATEGORY_CARD.items()))
    def test_each_io_category_has_its_home_card(self, category, card):
        assert candidates.home_card("io_candidates", {"category": category}) == card

    def test_entry_points_go_to_the_entry_catalog(self):
        assert candidates.home_card("entry_points", {"kind": "http-route"}) == "entry.catalog"

    def test_entities_go_to_data_entities_and_migrations_nowhere(self):
        assert candidates.home_card("models", {"kind": "enum"}) == "data.entities"
        assert candidates.home_card("models", {"kind": "migration"}) is None

    def test_unknown_category_has_no_home(self):
        assert candidates.home_card("io_candidates", {"category": "mystery"}) is None

    def test_other_outputs_have_no_home(self):
        assert candidates.home_card("dead", {"name": "x"}) is None


class TestForReport:
    def test_io_report_has_the_input_and_output_cards(self):
        got = candidates.for_report("io", build_extract())

        assert sorted(got) == ["io.inputs", "io.outputs"] and len(got["io.inputs"]) == 2 and len(got["io.outputs"]) == 2

    def test_data_report_has_only_entities(self):
        got = candidates.for_report("data", build_extract())

        assert list(got) == ["data.entities"] and [i["name"] for i in got["data.entities"]] == ["Item"]


class TestDispositions:
    def test_kept_and_dismissed_ids_are_listed_with_their_card(self):
        extract = build_extract()

        got = candidates.dispositions(reports_for(extract))

        kept = ids_where(extract, snippet='os.getenv("A")')[0]
        group = next(i["group"] for i in extract["io_candidates"] if i["path"] == "a.py" and i["category"] == "stdout")
        assert got[kept] == [("io", "io.inputs", "kept")] and got[group] == [("io", "io.inputs", "dismissed")]

    def test_entries_and_row_level_cand_on_entry_shaped_cards_count(self):
        reports = {"data": {"cards": [{"card": "data.entities", "entries": [{"name": "Item", "cand": ["md-1"]}]}]}}

        assert candidates.dispositions(reports) == {"md-1": [("data", "data.entities", "kept")]}


class TestOpenItems:
    def test_only_undecided_candidates_remain(self):
        extract = build_extract()

        got = candidates.open_items("io", extract, reports_for(extract))

        assert sorted((i["path"], i["line"]) for i in got) == [("a.py", 9), ("b.py", 2)]

    def test_a_group_id_covers_every_member(self):
        extract = build_extract()
        group = extract["io_candidates"][0]["group"]
        reports = {"io": {"cards": [{"card": "io.inputs", "dismissed": [{"cand": [group], "reason": "x"}]}]}}

        got = candidates.open_items("io", extract, reports)

        assert {i["category"] for i in got} == {"stdout"}

    def test_a_disposition_on_another_card_also_counts(self):
        extract = build_extract()
        ep = extract["entry_points"][0]["id"]
        reports = {"io": {"cards": [{"card": "io.inputs", "blocks": [{"type": "table", "rows": [{"cells": [], "cand": [ep]}]}]}]}}

        assert candidates.open_items("entry", extract, reports) == []

    def test_nothing_open_when_everything_is_decided(self):
        extract = build_extract()
        every = [i["id"] for i in extract["io_candidates"]]
        reports = {"io": {"cards": [{"card": "io.inputs", "dismissed": [{"cand": every, "reason": "x"}]}]}}

        assert candidates.open_items("io", extract, reports) == []


class TestText:
    def test_layout_per_card_group_and_hit(self):
        extract = build_extract()

        got = candidates.text("io", extract, {}, {}).splitlines()

        assert got[0] == "== io.inputs (Inputs): 2 findings in 1 groups =="
        group = extract["io_candidates"][0]["group"]
        assert got[1] == f"{group}  dossier.python.input.env-var  a.py  (2 hits: lines 3, 9)"
        assert got[2] == f"    {extract['io_candidates'][0]['id']}  a.py:3  os.getenv(\"A\")"

    def test_open_only_lists_the_undecided_and_nothing_when_all_are_decided(self):
        extract = build_extract()
        text = candidates.text("io", extract, reports_for(extract), {}, only_open=True)

        assert "a.py:3" not in text and "a.py:9" in text and "b.py:2" in text
        every = [i["id"] for i in extract["io_candidates"]]
        done = {"io": {"cards": [{"card": "io.inputs", "dismissed": [{"cand": every, "reason": "x"}]}]}}
        assert candidates.text("io", extract, done, {}, only_open=True) == ""

    def test_open_prints_nothing_for_reports_that_only_have_informational_lists(self):
        extract = {"graph": [{"kind": "module", "module": "p.a", "path": "p/a.py", "package": "p", "is_package": False}]}

        assert candidates.text("reading", extract, {}, {}, only_open=True) == ""
        assert candidates.text("components", extract, {}, {}, only_open=True) == ""

    def test_reading_lists_entry_files_test_files_and_ranked_modules(self):
        extract = {"graph": [{"kind": "module", "module": "p.a", "path": "p/a.py", "package": "p", "is_package": False},
                             {"kind": "module", "module": "p.b", "path": "p/b.py", "package": "p", "is_package": False},
                             {"kind": "import", "path": "p/a.py", "paths": ["p/b.py"], "from": "p.a", "to": "p.b", "lines": [1], "via": "grimp"}],
                   "entry_points": [{"path": "p/cli.py"}], "tests": [{"kind": "test-file", "path": "tests/test_a.py"}]}

        text = candidates.text("reading", extract, {}, {})

        assert text.index("p.b") < text.index("p.a") and "p/cli.py" in text and "tests/test_a.py" in text


class TestComponentCandidates:
    EXTRACT = {"graph": [
        {"kind": "module", "module": "app", "path": "src/app/__init__.py", "package": "app", "is_package": True},
        {"kind": "module", "module": "app.api", "path": "src/app/api/__init__.py", "package": "app", "is_package": True},
        {"kind": "module", "module": "app.api.routes", "path": "src/app/api/routes.py", "package": "app", "is_package": False},
        {"kind": "module", "module": "app.core", "path": "src/app/core.py", "package": "app", "is_package": False},
        {"kind": "import", "path": "src/app/api/routes.py", "paths": ["src/app/core.py"], "from": "app.api.routes", "to": "app.core", "lines": [1]}]}
    TREE = frozenset({"src/app/__init__.py", "src/app/api/__init__.py", "src/app/api/routes.py", "src/app/core.py", "README.md"})
    FACTS = {"chunks": {"chunks": [{"files": [{"path": "src/app/core.py", "lines": 40}, {"path": "src/app/api/routes.py", "lines": 10}]}]}}

    def test_folders_with_source_files_are_counted_with_lines(self):
        got = candidates.component_candidates(self.TREE, self.EXTRACT, self.FACTS)["folders"]

        assert {f["path"]: (f["files"], f["lines"]) for f in got} == {"src/app": (2, 40), "src/app/api": (2, 10)}

    def test_packages_come_from_the_graph_modules(self):
        got = candidates.component_candidates(self.TREE, self.EXTRACT, self.FACTS)["packages"]

        assert [p["package"] for p in got] == ["app", "app.api"]

    def test_communities_list_member_folders(self):
        got = candidates.component_candidates(self.TREE, self.EXTRACT, self.FACTS)["communities"]

        assert got and all(c["folders"] for c in got)


class TestJavaScriptSection:
    JS = {"graph": [{"kind": "source-root", "path": "apps/web/package.json", "root": "apps"},
                    {"kind": "module", "module": "apps/web/src/main", "short": "main", "path": "apps/web/src/main.tsx", "package": None,
                     "is_package": False, "language": "js"}]}

    def text(self, extract):
        return candidates.text("components", extract, {}, {}, tree={"apps/web/src/main.tsx"})

    def test_javascript_projects_are_listed(self):
        out = self.text(self.JS)

        assert "== JavaScript and TypeScript projects ==" in out and "apps  (1 modules)" in out

    def test_the_python_heading_is_left_out_when_only_javascript_exists(self):
        assert "== Python packages ==" not in self.text(self.JS)

    def test_a_python_repository_prints_what_it_printed_before(self):
        out = self.text(TestComponentCandidates.EXTRACT)

        assert "== Python packages ==" in out and "JavaScript and TypeScript" not in out


class TestCSharpSection:
    CS = {"graph": [{"kind": "cs-project", "path": "src/Shop.Api/Shop.Api.csproj", "name": "Shop.Api", "sdk": "Microsoft.NET.Sdk.Web",
                     "output_type": "Exe", "frameworks": ["net10.0"], "test": False, "packable": False, "references": []},
                    {"kind": "cs-project", "path": "tests/Shop.Tests/Shop.Tests.csproj", "name": "Shop.Tests", "sdk": "Microsoft.NET.Sdk",
                     "output_type": "Library", "frameworks": ["net10.0"], "test": True, "packable": False, "references": []},
                    {"kind": "source-root", "path": "src/Shop.Api/Shop.Api.csproj", "root": "src"},
                    {"kind": "module", "module": "src/Shop.Api/A", "short": "A", "path": "src/Shop.Api/A.cs", "project": "src/Shop.Api/Shop.Api.csproj",
                     "language": "csharp"},
                    {"kind": "module", "module": "src/Shop.Api/B", "short": "B", "path": "src/Shop.Api/B.cs", "project": "src/Shop.Api/Shop.Api.csproj",
                     "language": "csharp"}]}

    def text(self, extract):
        return candidates.text("components", extract, {}, {}, tree={"src/Shop.Api/A.cs", "src/Shop.Api/B.cs", "tests/Shop.Tests/A.cs",
                                                                    "tests/Shop.Tests/B.cs", "tests/Shop.Tests/C.cs"})

    def test_one_line_is_printed_per_project(self):
        out = self.text(self.CS).splitlines()

        i = out.index("== C# projects ==")
        assert out[i + 1] == "src/Shop.Api/Shop.Api.csproj  (SDK Microsoft.NET.Sdk.Web, Exe, 2 files)"
        assert out[i + 2] == "tests/Shop.Tests/Shop.Tests.csproj  (SDK Microsoft.NET.Sdk, Library, test project, 3 files)"

    def test_a_nested_project_does_not_take_its_parents_files(self):
        extract = {"graph": [{"kind": "cs-project", "path": "a/A.csproj", "name": "A", "sdk": "S", "output_type": "Library", "test": False},
                             {"kind": "cs-project", "path": "a/inner/I.csproj", "name": "I", "sdk": "S", "output_type": "Library", "test": False}]}

        out = candidates.text("components", extract, {}, {}, tree={"a/x.cs", "a/inner/y.cs", "a/inner/z.cs", "a/readme.md"})

        assert "a/A.csproj  (SDK S, Library, 1 files)" in out and "a/inner/I.csproj  (SDK S, Library, 2 files)" in out

    def test_a_csharp_only_extract_prints_no_python_packages_heading(self):
        assert "== Python packages ==" not in self.text(self.CS)

    def test_a_csharp_source_root_is_not_listed_as_a_javascript_project(self):
        assert "JavaScript and TypeScript" not in self.text(self.CS)

    def test_a_python_extract_prints_no_csharp_heading(self):
        assert "C# projects" not in candidates.text("components", TestComponentCandidates.EXTRACT, {}, {})


class TestCatalogEdges:
    ROWS = [{"name": "API", "paths": ["src/app/api/"]}, {"name": "Core", "paths": ["src/app/core.py"]}]
    EXTRACT = TestComponentCandidates.EXTRACT

    def test_imports_between_two_drafted_components_are_counted(self):
        assert candidates.catalog_edges(self.ROWS, self.EXTRACT) == [{"from": "API", "to": "Core", "imports": 1}]

    def test_catalog_rows_are_read_from_the_components_report(self):
        report = {"cards": [{"card": "components.catalog", "blocks": [{"type": "table", "rows": [
            {"cells": ["`API`", "`src/app/api/`, `scripts/*.sh`"]}, {"cells": ["Core", "src/app/core.py"]}]}]}]}

        assert candidates.catalog_rows(report) == [{"name": "API", "paths": ["src/app/api/", "scripts/*.sh"]},
                                                   {"name": "Core", "paths": ["src/app/core.py"]}]


class TestComponentOf:
    def rows(self, **paths):
        return [{"name": n, "paths": p} for n, p in paths.items()]

    def test_deeper_directory_beats_a_shallower_one(self):
        rows = self.rows(App=["src/app/"], Api=["src/app/api/"])

        assert component_of("src/app/api/x.py", rows) == ("Api", []) and component_of("src/app/core.py", rows) == ("App", [])

    def test_literal_file_beats_glob_and_glob_beats_directory(self):
        rows = self.rows(Dir=["scripts/"], Glob=["scripts/*.sh"], File=["scripts/seed.sh"])

        assert component_of("scripts/seed.sh", rows)[0] == "File" and component_of("scripts/run.sh", rows)[0] == "Glob"
        assert component_of("scripts/x.py", rows)[0] == "Dir"

    def test_two_components_matching_equally_are_both_reported(self):
        rows = self.rows(A=["src/x/"], B=["src/x/"])

        assert component_of("src/x/f.py", rows) == ("A", ["B"])

    def test_no_match_gives_none(self):
        assert component_of("docs/a.md", self.rows(A=["src/"])) == (None, [])

    def test_directory_pattern_does_not_match_a_sibling_with_the_same_prefix(self):
        assert component_of("src/application/x.py", self.rows(A=["src/app/"])) == (None, [])

    def test_parse_paths_strips_backticks_and_splits_on_commas(self):
        assert parse_paths("`src/a/`, scripts/*.sh,`x.py`") == ["src/a/", "scripts/*.sh", "x.py"]


def marker(path="src/a.py", line=3, rule="marker.hack", snippet="# HACK: skip"):
    return {"kind": "marker", "path": path, "line": line, "end_line": line, "rule": rule, "snippet": snippet}


def person(name, ident, kind="human", commits=5, commits_12m=2, **extra):
    return {"kind": "person", "path": "", "person": ident, "name": name, "type": kind, "commits": commits, "commits_12m": commits_12m,
            "assisted": 0, "first": "2024-01-01", "last": "2025-01-01", "aliases": [], "owned_commits": commits, "owned_lines": 0,
            "username": None, **extra}


def file_item(path, commits_12m=0, owners=None, blame=None, owner_lines=None, authors=None):
    return {"kind": "file", "path": path, "lines": 10, "commits": commits_12m, "commits_12m": commits_12m, "lines_changed": 0, "lines_changed_12m": 0,
            "last_changed": "2025-01-01", "authors": authors or {}, "blame": blame, "owners": owners or {}, "owner_lines": owner_lines}


META = {"kind": "meta", "path": "", "status": "ok", "reasons": []}


class TestHomeCardOfMarkers:
    def test_a_marker_belongs_to_the_decisions_card(self):
        assert candidates.home_card("history", marker()) == "change.decisions"

    def test_other_history_items_have_no_home(self):
        assert candidates.home_card("history", {"kind": "file", "path": "a.py"}) is None

    def test_the_change_report_lists_markers_as_findings(self):
        extract = {"history": candidates.assign_ids("history", [marker()])}

        assert list(candidates.for_report("change", extract)) == ["change.decisions"]

    def test_markers_are_open_until_a_row_keeps_or_a_group_dismisses_them(self):
        items = candidates.assign_ids("history", [marker(line=3), marker(line=9)])
        extract = {"history": items}
        kept = {"change": {"cards": [{"card": "change.decisions", "blocks": [{"type": "table", "rows": [{"cells": ["x"], "cand": [items[0]["group"]]}]}]}]}}

        assert len(candidates.open_items("change", extract, {})) == 2
        assert candidates.open_items("change", extract, kept) == []


class TestHistorySections:
    def extract(self):
        return {"history": [META, {"kind": "decision-doc", "path": "docs/adr/0001.md"},
                            {"kind": "long-commit", "path": "", "sha": "a" * 40, "subject": "Big change", "lines": 12, "files": 4},
                            {"kind": "todo", "path": "src/a.py", "count": 3}, {"kind": "todo", "path": "src/b.py", "count": 7},
                            {"kind": "bulk", "path": "", "sha": "b" * 40, "files": 900, "author": "Ann", "date": "2024-02-01", "subject": "Import"},
                            person("Ann Lee", "ann@x.org"), person("Ann", "a@y.org", commits=1), person("Bob Ray", "bob@x.org"),
                            {"kind": "assistant", "path": "", "name": "Claude", "commits": 4, "files": {"src/a.py": 2, "src/b.py": 3}},
                            file_item("src/a.py", 6, owners={"ann@x.org": 9, "bob@x.org": 1}, blame={"ann@x.org": 8}, owner_lines={"ann@x.org": 8}, authors={"ann@x.org": 10}),
                            file_item("src/b.py", 1, owners={"ann@x.org": 1, "bob@x.org": 1})],
                "symbols": [{"kind": "def", "path": "src/a.py", "line": 1, "name": "legacy_load"}, {"kind": "def", "path": "src/a.py", "line": 5, "name": "run", "symbol": "scip-python python pkg 1.0 pkg/a/run()."},
                            {"kind": "def", "path": "src/b.py", "line": 2, "name": "run", "symbol": "scip-python python pkg 1.0 pkg/b/run()."}, {"kind": "def", "path": "src/b.py", "line": 9, "name": "__init__"}],
                "graph": [{"kind": "cycle", "modules": ["a", "b"]}], "dead": [{"id": "dd-1"}]}

    def text(self, rid, **kw):
        catalog = {"cards": [{"card": "components.catalog", "blocks": [{"type": "table", "rows": [{"cells": ["Core", "src/"]}]}]}]}
        return candidates.text(rid, self.extract(), {"components": catalog}, {}, tree={"src/a.py", "src/b.py", "docs/adr/0001.md"}, **kw)

    def test_change_lists_documents_long_commits_todos_old_names_and_repeats(self):
        out = self.text("change")

        for title in ("== Decision documents ==", "== Long commit messages ==", "== TODO and FIXME counts ==", "== Old-looking names ==",
                      "== Same name defined more than once ==", "== Bulk commits =="):
            assert title in out
        assert "docs/adr/0001.md" in out and "src/b.py  7" in out and "legacy_load" in out and "run  in 2 files" in out
        assert "__init__" not in out

    def test_contributors_lists_people_duplicates_components_bulk_and_agents(self):
        out = self.text("contributors")

        assert "Ann Lee  (human)" in out and "Ann Lee  /  Ann" in out and "Bob Ray" in out
        assert "Core  (2 files, some without line data)" in out and "Ann Lee: 8 lines owned" in out
        assert "Claude: 4 human commits carry its marker, in 2 files" in out and "Import" in out
        assert "@" not in out

    def test_risks_lists_cycles_dead_code_and_single_owner_hotspots(self):
        out = self.text("risks")

        assert "1 import cycles" in out and "1 dead code findings" in out
        assert "src/a.py  6 commits in 12 months; Ann Lee owns 90% of its commits" in out

    def test_nothing_is_printed_with_open(self):
        assert self.text("contributors", only_open=True) == ""

    def test_no_history_prints_nothing(self):
        assert candidates.text("change", {"graph": []}, {}, {}, tree=set()) == ""
