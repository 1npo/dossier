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
