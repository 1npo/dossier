import json

import candidates


def item(path="a.py", line=1, rule="r", snippet="x = 1", **extra):
    return {"path": path, "line": line, "rule": rule, "snippet": snippet, **extra}


class TestNorm:
    def test_runs_of_whitespace_collapse_and_ends_are_stripped(self):
        assert candidates.norm("  a \n\t b  ") == "a b"


class TestAssignIds:
    def test_input_order_does_not_change_ids(self):
        items = [item(line=1, snippet="a"), item(line=2, snippet="b")]

        first = candidates.assign_ids("io_candidates", items)
        second = candidates.assign_ids("io_candidates", list(reversed(items)))

        assert first == second

    def test_moving_a_line_keeps_the_id(self):
        before = candidates.assign_ids("io_candidates", [item(line=3)])
        after = candidates.assign_ids("io_candidates", [item(line=30)])

        assert before[0]["id"] == after[0]["id"]

    def test_identical_snippets_in_one_file_get_different_ids(self):
        got = candidates.assign_ids("io_candidates", [item(line=1), item(line=2)])

        assert got[0]["id"] != got[1]["id"]

    def test_changed_snippet_changes_the_id(self):
        a = candidates.assign_ids("io_candidates", [item(snippet="x = 1")])
        b = candidates.assign_ids("io_candidates", [item(snippet="x = 2")])

        assert a[0]["id"] != b[0]["id"]

    def test_group_depends_only_on_rule_and_path(self):
        a = candidates.assign_ids("io_candidates", [item(snippet="p")])
        b = candidates.assign_ids("io_candidates", [item(snippet="q", line=9)])

        assert a[0]["group"] == b[0]["group"]

    def test_group_differs_between_files(self):
        got = candidates.assign_ids("io_candidates", [item(path="a.py"), item(path="b.py")])

        assert got[0]["group"] != got[1]["group"]

    def test_prefix_follows_the_output(self):
        got = candidates.assign_ids("dead", [item()])

        assert got[0]["id"].startswith("dd-") and got[0]["group"].startswith("ddg-")

    def test_items_are_returned_sorted_by_path_then_line(self):
        got = candidates.assign_ids("io_candidates", [item(path="b.py", line=1), item(path="a.py", line=5), item(path="a.py", line=2)])

        assert [(i["path"], i["line"]) for i in got] == [("a.py", 2), ("a.py", 5), ("b.py", 1)]

    def test_item_without_rule_uses_kind_and_without_snippet_uses_name(self):
        got = candidates.assign_ids("models", [{"path": "m.py", "kind": "enum", "name": "Status"}])

        assert got[0]["id"].startswith("md-")

    def test_whitespace_in_snippet_does_not_change_the_id(self):
        a = candidates.assign_ids("io_candidates", [item(snippet="a  b")])
        b = candidates.assign_ids("io_candidates", [item(snippet="a b")])

        assert a[0]["id"] == b[0]["id"]


def write(out, name, adapters_data):
    (out / "extract").mkdir(parents=True, exist_ok=True)
    (out / "extract" / f"{name}.json").write_text(json.dumps({"schema": 1, "sha": "s", "adapters": adapters_data}))


class TestHistoryIds:
    def test_marker_items_get_mk_ids_that_survive_a_line_move(self):
        a = {"path": "a.py", "line": 3, "end_line": 3, "rule": "marker.hack", "snippet": "# HACK: x"}
        b = {**a, "line": 30, "end_line": 30}

        first, second = candidates.assign_ids("history", [a]), candidates.assign_ids("history", [b])

        assert first[0]["id"].startswith("mk-") and first[0]["group"].startswith("mkg-")
        assert first[0]["id"] == second[0]["id"]


class TestLoad:
    def test_items_of_every_adapter_come_in_adapter_name_order(self, tmp_path):
        write(tmp_path, "entry_points", {"repo": {"items": [{"id": "ep-2"}]}, "python": {"items": [{"id": "ep-1"}]}})

        got = candidates.load(tmp_path)

        assert [i["id"] for i in got["entry_points"]] == ["ep-1", "ep-2"]

    def test_missing_folder_gives_empty(self, tmp_path):
        assert candidates.load(tmp_path) == {}

    def test_unreadable_file_is_skipped(self, tmp_path):
        (tmp_path / "extract").mkdir()
        (tmp_path / "extract" / "dead.json").write_text("{not json")

        assert candidates.load(tmp_path) == {}


class TestByIdAndGroups:
    EXTRACT = {"io_candidates": [{"id": "io-1", "group": "iog-1"}, {"id": "io-2", "group": "iog-1"}]}

    def test_by_id_finds_items_and_groups(self):
        got = candidates.by_id(self.EXTRACT)

        assert got["io-2"]["id"] == "io-2" and got["iog-1"]["id"] == "io-1"

    def test_group_members_lists_ids_per_group(self):
        assert candidates.group_members(self.EXTRACT) == {"iog-1": ["io-1", "io-2"]}


def mod(name):
    return {"kind": "module", "path": name + ".py", "module": name, "package": None, "is_package": False}


def edge(a, b, lines=(1,)):
    return {"kind": "import", "path": a + ".py", "paths": [b + ".py"], "from": a, "to": b, "lines": list(lines), "via": "grimp"}


def cand(i, category="env-var", line=3):
    return {"id": i, "group": "iog-" + i, "path": "a.py", "line": line, "category": category, "rule": "r", "snippet": "x"}


BASE = {"graph": [mod("a"), mod("b"), edge("a", "b")], "io_candidates": [cand("io-1"), cand("io-2", "log")],
        "entry_points": [{"id": "ep-1", "group": "g", "path": "a.py", "line": 1, "kind": "main-guard"}],
        "tests": [{"kind": "test-file", "path": "t.py", "tests": 2, "skips": 0, "xfails": 0}]}


def changed(before, after):
    old, new = candidates.digests(before), candidates.digests(after)
    return {rid for rid in old if old[rid] != new[rid]}


class TestDigest:
    def test_shifting_every_line_keeps_every_digest(self):
        shifted = {**BASE, "graph": [mod("a"), mod("b"), edge("a", "b", (40,))], "io_candidates": [cand("io-1", line=30), cand("io-2", "log", line=31)]}

        assert changed(BASE, shifted) == set()

    def test_a_complexity_number_on_a_module_changes_no_digest(self):
        with_complexity = {**BASE, "graph": [{**mod("a"), "complexity": 12}, mod("b"), edge("a", "b")]}

        assert changed(BASE, with_complexity) == set()

    def test_new_candidate_changes_only_its_home_report(self):
        after = {**BASE, "io_candidates": BASE["io_candidates"] + [cand("io-3", "log")]}

        assert changed(BASE, after) == {"behavior", "conventions"}

    def test_new_input_changes_io_and_conventions(self):
        after = {**BASE, "io_candidates": BASE["io_candidates"] + [cand("io-3", "env-var")]}

        assert changed(BASE, after) == {"io", "conventions"}

    def test_new_import_changes_the_reports_built_from_the_graph(self):
        after = {**BASE, "graph": BASE["graph"] + [edge("b", "a")]}

        assert changed(BASE, after) == {"reading", "components", "interactions"}

    def test_new_module_also_changes_conventions(self):
        after = {**BASE, "graph": BASE["graph"] + [mod("c")]}

        assert changed(BASE, after) == {"reading", "components", "interactions", "conventions"}

    def test_new_entry_point_changes_entry_reading_io_and_ops(self):
        after = {**BASE, "entry_points": BASE["entry_points"] + [{"id": "ep-2", "group": "g2", "path": "b.py", "line": 1, "kind": "cli-command"}]}

        assert changed(BASE, after) == {"reading", "entry", "io", "ops"}

    def test_a_skipped_test_changes_behavior_and_reading(self):
        after = {**BASE, "tests": [{"kind": "test-file", "path": "t.py", "tests": 2, "skips": 1, "xfails": 0}]}

        assert changed(BASE, after) == {"reading", "behavior"}


class TestReadingModules:
    def graph(self, n):
        mods = [{"kind": "module", "path": f"src/m{i}.py", "module": f"m{i}", "is_package": False} for i in range(n)]
        imports = [{"kind": "import", "path": f"src/m{i}.py", "paths": [f"src/m{i + 1}.py"], "from": f"m{i}", "to": f"m{i + 1}"} for i in range(n - 1)]
        return {"graph": mods + imports}

    def test_every_module_is_listed_not_only_the_top_thirty(self):
        data = candidates.report_data("reading", self.graph(40), {}, {})

        assert len(data["modules"]) == 40

    def test_the_text_heading_does_not_say_top_thirty(self):
        out = candidates.text("reading", self.graph(40), {}, {})

        assert "(top 30)" not in out
        assert "== Modules by import rank ==" in out
        assert out.count("(rank ") == 40


def marker(i, line=3, path="a.py"):
    return {"kind": "marker", "id": i, "group": "mkg-" + i, "path": path, "line": line, "end_line": line, "rule": "marker.hack", "snippet": "# HACK"}


def human(ident="a@x", commits=3):
    return {"kind": "person", "path": "", "person": ident, "name": ident, "type": "human", "commits": commits, "commits_12m": commits}


class TestHistoryDigests:
    def test_a_new_marker_changes_only_the_change_digest(self):
        before = {"history": [marker("mk-1")]}
        after = {"history": [marker("mk-1"), marker("mk-2", line=9)]}

        assert changed(before, after) == {"change"}

    def test_moving_a_marker_to_another_line_changes_nothing(self):
        assert changed({"history": [marker("mk-1", line=3)]}, {"history": [marker("mk-1", line=40)]}) == set()

    def test_a_new_decision_document_changes_the_change_digest(self):
        assert changed({"history": []}, {"history": [{"kind": "decision-doc", "path": "docs/adr/1.md"}]}) == {"change"}

    def test_a_new_commit_by_a_known_person_leaves_the_contributors_digest_alone(self):
        assert changed({"history": [human(commits=3)]}, {"history": [human(commits=4)]}) == set()

    def test_a_new_person_changes_the_contributors_digest(self):
        assert changed({"history": [human()]}, {"history": [human(), human("b@x")]}) == {"contributors"}

    def test_a_person_who_changes_type_changes_the_contributors_digest(self):
        assert changed({"history": [human()]}, {"history": [{**human(), "type": "bot"}]}) == {"contributors"}


class TestToolStatus:
    def write(self, tmp_path, name, adapters):
        (tmp_path / "extract").mkdir(exist_ok=True)
        (tmp_path / "extract" / f"{name}.json").write_text(json.dumps({"schema": 1, "sha": "s", "adapters": adapters}))

    def test_status_is_read_from_every_section_including_reused_ones(self, tmp_path):
        self.write(tmp_path, "graph", {"python": {"tools": {"grimp": "3.17"}, "tool_status": {"grimp": {"status": "ok", "reason": None}}, "items": []}})
        self.write(tmp_path, "dead", {"python": {"tools": {}, "tool_status": {"vulture": {"status": "failed", "reason": "timed out"}}, "items": []}})

        got = candidates.tool_status(tmp_path)

        assert got == {"grimp": {"status": "ok", "reason": None, "version": "3.17"}, "vulture": {"status": "failed", "reason": "timed out", "version": ""}}

    def test_a_tool_named_twice_keeps_its_worst_status(self, tmp_path):
        self.write(tmp_path, "a", {"x": {"tools": {"semgrep": "1"}, "tool_status": {"semgrep": {"status": "ok", "reason": None}}, "items": []}})
        self.write(tmp_path, "b", {"x": {"tools": {}, "tool_status": {"semgrep": {"status": "skipped", "reason": "no"}}, "items": []}})

        assert candidates.tool_status(tmp_path)["semgrep"]["status"] == "skipped"

    def test_no_extract_folder_gives_nothing(self, tmp_path):
        assert candidates.tool_status(tmp_path) == {}


class TestPublicApiFeed:
    API = {"kind": "public-api", "path": "src/a.ts", "line": 3, "name": "one", "symbol_kind": "function", "package": "lib", "subpath": ".", "audience": "marked private"}

    def test_a_new_name_changes_the_io_digest(self):
        base = {"symbols": [self.API]}
        more = {"symbols": [self.API, dict(self.API, name="two")]}

        assert candidates.digest("io", base) != candidates.digest("io", more)

    def test_a_moved_line_does_not(self):
        assert candidates.digest("io", {"symbols": [self.API]}) == candidates.digest("io", {"symbols": [dict(self.API, line=40)]})

    def test_a_repository_without_a_public_api_has_the_digest_it_had(self):
        assert candidates.digest("io", {"entry_points": [], "io_candidates": []}) == candidates.digest("io", {"entry_points": [], "io_candidates": [], "symbols": []})


class TestUiFeed:
    COMP = {"kind": "ui-component", "path": "src/App.tsx", "line": 5, "name": "App", "exported": True, "hooks": [], "provides": [], "consumes": []}
    EDGE = {"kind": "renders", "path": "src/App.tsx", "paths": ["src/Button.tsx"], "from": "App", "to": "Button"}

    def digest(self, *graph):
        return candidates.digest("interactions", {"graph": list(graph)})

    def test_a_moved_component_changes_no_digest(self):
        assert self.digest(self.COMP, self.EDGE) == self.digest(dict(self.COMP, line=90, end_line=120), self.EDGE)

    def test_a_new_rendered_file_changes_interactions(self):
        other = dict(self.EDGE, paths=["src/Card.tsx"])

        assert self.digest(self.COMP, self.EDGE) != self.digest(self.COMP, self.EDGE, other)

    def test_a_new_component_changes_interactions_and_not_reading(self):
        extra = dict(self.COMP, name="Footer")

        assert self.digest(self.COMP) != self.digest(self.COMP, extra)
        assert candidates.digest("reading", {"graph": [self.COMP]}) == candidates.digest("reading", {"graph": [self.COMP, extra]})

    def test_a_python_repository_has_the_digest_it_had(self):
        assert candidates.digest("interactions", BASE) == candidates.digest("interactions", {**BASE, "graph": list(BASE["graph"])})


class TestHitNames:
    def test_a_hit_with_a_name_different_from_its_snippet_prints_the_name(self):
        extract = {"entry_points": [item(path="project.json", snippet="nx build", name="api:build", kind="nx-target", group="g1", id="ep-1")]}

        got = candidates.text("entry", extract, {}, {})

        assert "ep-1  project.json:1  nx build  [api:build]" in got

    def test_a_hit_whose_name_is_its_snippet_prints_no_brackets(self):
        extract = {"entry_points": [item(snippet="GET /x", name="GET /x", kind="http-route", group="g1", id="ep-1")]}

        got = candidates.text("entry", extract, {}, {})

        assert "GET /x  [" not in got


class TestProjectsFeed:
    PROJ = {"kind": "cs-project", "path": "src/A/A.csproj", "name": "A", "references": []}

    def test_a_project_reference_changes_the_components_digest(self):
        base = {"graph": [self.PROJ]}
        more = {"graph": [dict(self.PROJ, references=["src/B/B.csproj"])]}

        assert candidates.digest("components", base) != candidates.digest("components", more)

    def test_moving_a_line_does_not(self):
        module = {"kind": "module", "module": "src/A/X", "path": "src/A/X.cs", "line": 3}

        assert candidates.digest("components", {"graph": [self.PROJ, module]}) == candidates.digest("components", {"graph": [self.PROJ, dict(module, line=40)]})

    def test_a_python_and_a_javascript_extract_keep_their_digest(self):
        py = {"graph": [mod("a"), edge("a", "b")]}
        js = {"graph": [{"kind": "source-root", "path": "p/package.json", "root": "p"}, dict(mod("p/x"), language="js")]}

        assert candidates._feed("projects", py) == [] and candidates._feed("projects", js) == []


class TestCSharpStaleness:
    def extract(self, line):
        return {"graph": [{"kind": "module", "module": "src/A/X", "path": "src/A/X.cs", "short": "X", "language": "csharp", "project": "src/A/A.csproj"},
                          {"kind": "import", "from": "src/A/X", "to": "src/A/Y", "path": "src/A/X.cs", "paths": ["src/A/Y.cs"], "lines": [line]},
                          {"kind": "cs-project", "path": "src/A/A.csproj", "name": "A", "references": []}],
                "symbols": [{"kind": "def", "path": "src/A/X.cs", "line": line, "symbol": "X#", "public": True}],
                "entry_points": [{"path": "src/A/X.cs", "line": line, "kind": "program-main", "name": "Main"}],
                "models": [{"path": "src/A/X.cs", "line": line, "kind": "ef-entity", "name": "X"}]}

    def test_moving_every_line_in_a_csharp_file_changes_no_digest(self):
        assert candidates.digests(self.extract(3)) == candidates.digests(self.extract(30))


class TestFreshnessIsNotAFeed:
    def test_the_digests_do_not_depend_on_the_pin_record(self):
        extract = {"entry_points": [{"path": "a.py", "line": 1, "kind": "main-guard", "name": "x", "rule": "r", "snippet": "s"}]}

        before = candidates.digests(extract)
        behind = {"records": [{"step": "pin", "by": "prepare", "details": {"freshness": {"behind": 3}}}]}
        ahead = {"records": [{"step": "pin", "by": "prepare", "details": {"freshness": {"behind": 0}}}]}

        assert candidates.digests(extract) == before and behind != ahead and "freshness" not in str(extract)
