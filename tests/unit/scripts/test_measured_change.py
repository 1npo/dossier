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
    rows = re.findall(r"<tr>(.*?)</tr>", re.search(r"<tbody>(.*?)</tbody>", table, re.S).group(1), re.S)
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
        assert rows[3][2:5] == ["0", "0", "0"]

    def test_sorted_by_recent_commits_then_complexity_then_path(self):
        graph = [{"kind": "module", "path": "src/b.py", "complexity": 7}, {"kind": "module", "path": "src/a.py", "complexity": 2}]

        rows = cells(draw("change.hotspots", ctx(hist(*FILES), TREE, graph=graph)), "t-change-hotspots-files")

        assert [r[0] for r in rows][:2] == ["src/b.py", "src/a.py"]
        assert rows[0][5] == "7" and rows[2][5] == "-"

    def test_sentence_counts_files_that_did_not_change(self):
        html = draw("change.hotspots", ctx(hist(*FILES), TREE))

        assert "Every source file, most changed in the 12 months before this commit first. 2 of 4 files did not change in that time." in html

    def test_scatter_has_one_circle_and_one_title_per_file(self):
        html = draw("change.hotspots", ctx(hist(*FILES), TREE))

        assert html.count("<circle") == 4 and html.count("<title>") == 4
        assert "src/a.py: 5 commits, 100 lines" in html
        assert 'width="640" height="320"' in html and 'class="chart-scroll"' in html and 'role="img"' in html

    def test_scatter_text_is_at_least_12px(self):
        html = draw("change.hotspots", ctx(hist(*FILES), TREE))

        assert set(re.findall(r'<text[^>]*font-size="(\d+)"', html)) == {"12"}

    def test_component_table_sums_file_counts(self):
        catalog = [{"name": "core", "paths": ["src/"]}, {"name": "empty", "paths": ["nothing/"]}]

        rows = cells(draw("change.hotspots", ctx(hist(*FILES), TREE, catalog)), "t-change-hotspots-components")

        assert rows == [["core", "4", "10", "160", "0"], ["empty", "0", "0", "0", "0"]]

    def test_without_a_catalog_the_component_cell_is_a_dash_and_the_table_says_why(self):
        html = draw("change.hotspots", ctx(hist(*FILES), TREE))

        assert cells(html, "t-change-hotspots-files")[0][1] == "-"
        assert 'none-found' in html and "t-change-hotspots-components" not in html

    def test_no_source_files_leaves_the_placeholder(self):
        assert draw("change.hotspots", ctx(hist(*FILES), ["README.md"])) is None
