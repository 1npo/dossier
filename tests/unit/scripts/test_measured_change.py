import re

import measured
import measured_change
import render


class Refs:
    def mark(self, cites):
        return f"[{','.join(cites)}]"


def hist(*files, **meta):
    items = [{"kind": "meta", "path": "", "status": "ok", "reasons": [], **meta}]
    for path, c12, call, lines, last in files:
        items.append({"kind": "file", "path": path, "commits_12m": c12, "commits": call, "lines": lines, "last_changed": last})
    return items


def ctx(history, tree, catalog=None, graph=()):
    return {"extract": {"history": history, "graph": list(graph)}, "tree": set(tree), "catalog": catalog or [], "facts": {}}


def draw(cid, c):
    return measured.body(cid, c, Refs())


def cells(html, tid):
    table = re.search(rf'<table class="table[^"]*" id="{tid}">(.*?)</table>', html, re.S).group(1)
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", re.search(r"<tbody>(.*?)</tbody>", table, re.S).group(1), re.S)
    return [[re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)] for r in rows]


FILES = [("src/a.py", 5, 9, 100, "2026-05-01"), ("src/b.py", 5, 6, 50, "2026-04-01"), ("src/c.py", 0, 3, 10, "2024-01-01")]
TREE = ["src/a.py", "src/b.py", "src/c.py", "src/d.py", "README.md"]


class TestHotspots:
    def test_no_history_leaves_the_placeholder(self):
        assert draw("change.hotspots", ctx([], TREE)) is None

    def test_one_row_per_source_file_including_files_with_no_commits(self):
        html = draw("change.hotspots", ctx(hist(*FILES), TREE))

        rows = cells(html, "t-change-hotspots-files")
        assert [r[0] for r in rows] == ["src/a.py", "src/b.py", "src/c.py", "src/d.py"]
        assert rows[3][2] == "0"

    def test_sorted_by_recent_commits_then_complexity_then_path(self):
        graph = [{"kind": "module", "path": "src/b.py", "complexity": 7}, {"kind": "module", "path": "src/a.py", "complexity": 2}]

        rows = cells(draw("change.hotspots", ctx(hist(*FILES), TREE, graph=graph)), "t-change-hotspots-files")

        assert [r[0] for r in rows][:2] == ["src/b.py", "src/a.py"]
        assert rows[0][5] == "7" and rows[2][5] == "-"

    def test_there_is_no_subtitle_and_no_scatter(self):
        html = draw("change.hotspots", ctx(hist(*FILES), TREE))

        assert "Every source file" not in html and "<circle" not in html and "scatter" not in html

    def test_component_table_sums_file_counts(self):
        catalog = [{"name": "core", "paths": ["src/"]}, {"name": "empty", "paths": ["nothing/"]}]

        rows = cells(draw("change.hotspots", ctx(hist(*FILES), TREE, catalog)), "t-change-hotspots-components")

        assert rows == [["core", "4", "10", "-", "-", "0"], ["empty", "0", "0", "-", "-", "0"]]

    def test_without_a_catalog_the_component_cell_is_a_dash_and_the_table_says_why(self):
        html = draw("change.hotspots", ctx(hist(*FILES), TREE))

        assert cells(html, "t-change-hotspots-files")[0][1] == "-"
        assert 'none-found' in html and "t-change-hotspots-components" not in html

    def test_one_table_per_view_behind_a_file_or_component_toggle(self):
        catalog = [{"name": "core", "paths": ["src/"]}]

        html = draw("change.hotspots", ctx(hist(*FILES), TREE, catalog))

        assert re.findall(r'data-hot-set="(\w+)" aria-pressed="(\w+)"', html) == [("files", "true"), ("components", "false")]
        assert 'data-hot="files">' in html and 'data-hot="components" hidden>' in html

    def test_added_and_removed_lines_have_their_own_columns_and_a_dash_when_unknown(self):
        items = hist(*FILES)
        items[1].update(lines_added_12m=30, lines_deleted_12m=4)

        rows = cells(draw("change.hotspots", ctx(items, TREE)), "t-change-hotspots-files")

        assert measured_change.HOTSPOT_FILES[2:5] == ["Commits", "Lines added", "Lines removed"] and "Lines" not in measured_change.HOTSPOT_FILES
        assert [r[3:5] for r in rows if r[0] == items[1]["path"]] == [["+30", "\u22124"]] and rows[-1][3:5] == ["-", "-"]

    def test_no_column_name_mentions_a_time_frame(self):
        assert not [c for c in measured_change.HOTSPOT_FILES + measured_change.HOTSPOT_COMPONENTS if "month" in c or "all" in c.lower()]

    def test_a_period_toggle_shows_the_past_12_months_or_all_time(self):
        items = hist(*FILES)
        items[1].update(lines_added=300, lines_deleted=40, lines_added_12m=30, lines_deleted_12m=4)
        catalog = [{"name": "core", "paths": ["src/"]}]

        html = draw("change.hotspots", ctx(items, TREE, catalog))

        assert re.findall(r'data-hotperiod-set="(\w+)" aria-pressed="(\w+)"', html) == [("12m", "true"), ("all", "false")]
        assert html.count('data-hotperiod="12m"') == 2 and html.count('data-hotperiod="all" hidden>') == 2
        recent, ever = cells(html, "t-change-hotspots-files"), cells(html, "t-change-hotspots-files-all")
        assert [r[2] for r in recent[:2]] == ["5", "5"] and [r[0] for r in ever[:2]] == ["src/a.py", "src/b.py"]
        assert [r[2] for r in ever[:3]] == ["9", "6", "3"] and [r for r in ever if r[0] == "src/a.py"][0][2] == "9"
        assert [r[3:5] for r in ever if r[0] == "src/a.py"] == [["+300", "\u221240"]]
        assert cells(html, "t-change-hotspots-components-all")[0][:3] == ["core", "4", "18"]

    def test_one_file_table_with_the_top_rows_marked_and_a_top_all_toggle(self):
        html = draw("change.hotspots", ctx(hist(*FILES), TREE))

        assert "hot-box" not in html and "hot-rank" not in html
        assert re.findall(r'data-hotshow-set="(\w+)" aria-pressed="(\w+)"', html) == [("top", "true"), ("all", "false")]
        assert html.count('<table class="table hot-files"') == 2
        files = html.split('id="t-change-hotspots-files"')[1].split("</table>")[0]
        assert files.count('<tr class="hot-top">') == 2   # a.py and b.py changed; c.py did not

    def test_no_source_files_leaves_the_placeholder(self):
        assert draw("change.hotspots", ctx(hist(*FILES), ["README.md"])) is None


def pair(a, b, co, share=50):
    return {"kind": "pair", "path": a, "a": a, "b": b, "co_commits": co, "commits_a": 5, "commits_b": 5, "share": share}


def imp(a, b):
    return {"kind": "import", "path": a, "paths": [b], "from": a, "to": b}


def mod(path):
    return {"kind": "module", "path": path, "module": path[:-3].replace("/", ".")}


class TestLinked:
    def test_direct_import_in_either_direction_is_yes(self):
        extract = {"graph": [mod("a.py"), mod("b.py"), imp("a.py", "b.py")]}

        assert measured_change.linked("b.py", "a.py", extract) == "yes"

    def test_both_covered_and_nothing_joins_them_is_no(self):
        assert measured_change.linked("a.py", "b.py", {"graph": [mod("a.py"), mod("b.py")]}) == "no"

    def test_an_uncovered_file_is_not_in_the_graph(self):
        assert measured_change.linked("a.py", "x.js", {"graph": [mod("a.py")]}) == "not in the graph"

    def test_a_pair_joined_only_by_a_tests_imports_is_yes(self):
        extract = {"graph": [mod("a.py")], "tests": [{"kind": "test-file", "path": "tests/test_a.py", "paths": ["a.py"]}]}

        assert measured_change.linked("a.py", "tests/test_a.py", extract) == "yes"

    def test_a_reference_edge_counts(self):
        extract = {"graph": [mod("a.py"), mod("b.py")], "symbols": [{"kind": "ref-edge", "path": "a.py", "paths": ["b.py"]}]}

        assert measured_change.linked("a.py", "b.py", extract) == "yes"


class TestCochange:
    def test_lists_pairs_with_three_or_more_commits_sorted(self):
        history = hist(pairs_total=4) + [pair("a.py", "b.py", 3, 60), pair("a.py", "c.py", 7, 40), pair("b.py", "c.py", 2)]
        c = ctx(history, ["a.py"], graph=[mod("a.py"), mod("b.py")])

        html = draw("change.cochange", c)

        rows = cells(html, "t-change-cochange")
        assert [(r[0], r[1], r[2], r[3], r[4]) for r in rows] == [("a.py", "c.py", "7", "40%", "not in the graph"), ("a.py", "b.py", "3", "60%", "no")]
        assert "(2 of 4 pairs)" in html and "more than 400 files are left out" in html

    def test_no_pair_says_none_found(self):
        html = draw("change.cochange", ctx(hist(pairs_total=1) + [pair("a.py", "b.py", 2)], ["a.py"]))

        assert "none-found" in html and "<table" not in html


class TestDeadRows:
    def test_includes_tool_items_unused_dependencies_and_modules_nothing_imports(self):
        extract = {"dead": [{"name": "f", "type": "function", "message": "unused function 'f'", "confidence": 60, "path": "a.py", "line": 3}],
                   "graph": [mod("a.py"), mod("b.py"), mod("pkg/__init__.py"), mod("c.py"), imp("a.py", "b.py")],
                   "entry_points": [{"path": "c.py"}]}

        got = measured_change.dead_rows(extract, {"unused": [{"n": "left-pad", "note": "No file imports it."}]})

        assert [(g[0], g[1]) for g in got] == [("f", "function"), ("left-pad", "unused dependency"), ("a", "module nothing imports")]
        assert got[0][2] == "unused function 'f' (60% confidence)"

    def test_a_finding_with_no_confidence_has_no_percentage(self):
        extract = {"dead": [{"name": "x.ts", "type": "unused file", "message": "No entry point or other file uses this file.",
                             "confidence": None, "path": "src/x.ts", "line": None}]}

        got = measured_change.dead_rows(extract, None)

        assert got[0][2] == "No entry point or other file uses this file."

    def test_a_javascript_module_nothing_imports_is_left_to_knip(self):
        js = {"kind": "module", "module": "src/a", "path": "src/a.ts", "language": "js"}

        assert measured_change.dead_rows({"graph": [js]}, None) == []

    def test_a_knip_dependency_replaces_the_same_name_from_the_dependency_report(self):
        extract = {"dead": [{"name": "left-pad", "type": "unused dependency", "message": "Not imported.", "confidence": None, "path": "package.json", "line": None}]}

        got = measured_change.dead_rows(extract, {"unused": [{"n": "left-pad", "note": "No file imports it."}, {"n": "other", "note": "No file imports it."}]})

        assert [(g[0], g[1]) for g in got] == [("left-pad", "unused dependency"), ("other", "unused dependency")]
        assert got[0][2] == "Not imported."

    def test_card_has_the_caveat_and_a_row_per_finding(self):
        c = ctx(hist(), TREE, graph=[mod("a.py")])
        c["extract"]["dead"] = []

        html = draw("change.dead-code", c)

        assert "Tool output, not checked by a person" in html
        assert [r[:2] for r in cells(html, "t-change-dead-code")] == [["a", "module nothing imports"]]

    def test_nothing_found_says_so(self):
        c = ctx(hist(), TREE, graph=[mod("a.py"), mod("b.py"), imp("b.py", "a.py"), imp("a.py", "b.py")])
        c["extract"]["dead"] = []

        assert "none-found" in draw("change.dead-code", c)


class TestInFlight:
    BRANCH = {"kind": "branch", "path": "", "ref": "origin/feat-y", "sha": "a" * 40, "date": "2026-05-01", "ahead": 2, "behind": 1, "author": "Bob", "remote": True}

    def test_branch_row(self):
        html = draw("change.in-flight", ctx(hist() + [self.BRANCH], TREE))

        assert cells(html, "t-change-in-flight")[0][:4] == ["origin/feat-y", "2026-05-01 aaaaaaa", "2 ahead, 1 behind", "Bob"]
        assert "no remote branches" not in html

    def test_local_branches_are_labelled(self):
        html = draw("change.in-flight", ctx(hist() + [{**self.BRANCH, "remote": False}], TREE))

        assert "This repository has no remote branches, so these are local branches." in html

    def test_none_found(self):
        assert "none-found" in draw("change.in-flight", ctx(hist(), TREE))


class TestCochangeCard:
    def c(self, *pairs, tree=("a.py", "b.py", "c.py", "d.py", "e.py")):
        return ctx(hist(pairs_total=len(pairs)) + [pair(a, b, n, share) for a, b, n, share in pairs], tree)

    def test_the_card_has_no_cluster_view_and_the_share_note_is_at_the_end(self):
        html = draw("change.cochange", self.c(("a.py", "b.py", 5, 80), ("b.py", "c.py", 4, 60), ("a.py", "c.py", 4, 70)))

        assert "cluster" not in html and "data-cc" not in html and html.rstrip().endswith("changed in the same commit.</li></ul>") and html.count("<li>") == 2
        assert "Share is" not in html.split("<table")[0]
