import base64
import json
import re

import measured
import measured_blast


class Refs:
    def mark(self, cites):
        return ""


def mod(path):
    return {"kind": "module", "path": path, "module": path[:-3]}


def imp(a, b):
    return {"kind": "import", "path": a, "paths": [b], "from": a, "to": b}


def ctx(extra=None):
    extract = {"graph": [mod("a.py"), mod("b.py"), mod("c.py"), imp("a.py", "b.py"), imp("b.py", "c.py")],
               "tests": [{"kind": "test-file", "path": "tests/test_a.py", "paths": ["a.py"]}],
               "blindspots": [{"id": "bs-1"}, {"id": "bs-2"}],
               "history": [{"kind": "meta"}, {"kind": "pair", "a": "b.py", "b": "d.py", "co_commits": 4, "share": 50, "path": "b.py"},
                           {"kind": "pair", "a": "c.py", "b": "d.py", "co_commits": 2, "share": 50, "path": "c.py"}]}
    extract.update(extra or {})
    return {"extract": extract, "tree": {"a.py", "b.py", "c.py", "d.py", "README.md"}, "catalog": [{"name": "core", "paths": ["a.py", "b.py"]}], "facts": {}}


def decode(b64, n):
    raw = base64.b64decode(b64)
    return {j for j in range(n) if raw[j >> 3] & (1 << (j & 7))}


class TestData:
    def test_files_are_the_source_files_plus_graph_modules_sorted(self):
        d = measured_blast.data(ctx())

        assert d["files"] == ["a.py", "b.py", "c.py", "d.py"] and d["graph"] == [1, 1, 1, 0]

    def test_bits_decode_back_to_the_closure(self):
        d = measured_blast.data(ctx())

        assert decode(d["dep"][2], 4) == {0, 1}
        assert decode(d["dep"][0], 4) == set() and d["dep"][3] == ""

    def test_direct_counts_and_components(self):
        d = measured_blast.data(ctx())

        assert d["direct"] == [0, 1, 1, 0] and d["components"] == ["core"] and d["component"] == [0, 0, -1, -1]

    def test_tests_and_co_changes_are_indexed(self):
        d = measured_blast.data(ctx())

        assert d["tests"] == ["tests/test_a.py"] and d["ft"][0] == [0] and d["ft"][1] == []
        assert d["co"] == {"b.py": [["d.py", 4]], "d.py": [["b.py", 4]]}

    def test_no_files_gives_none(self):
        assert measured_blast.data({"extract": {}, "tree": set()}) is None


class TestCard:
    def html(self):
        return measured.body("change.blast-radius", ctx(), Refs())

    def test_table_has_one_row_per_file_with_data_file(self):
        html = self.html()

        assert re.findall(r'<tr data-file="(\d+)">', html) == ["0", "1", "2", "3"]

    def test_files_outside_the_graph_say_so(self):
        html = self.html()
        row = re.findall(r'<tr data-file="3">(.*?)</tr>', html, re.S)[0]

        assert row.count("not in the graph") == 2

    def test_dependents_include_tests_reached_through_the_closure(self):
        html = self.html()
        cells = [re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<td[^>]*>(.*?)</td>", re.findall(r'<tr data-file="2">(.*?)</tr>', html, re.S)[0], re.S)]

        assert cells[2:] == ["1", "2", "1", "0"]

    def test_picker_lists_components_and_files_and_the_data_parses(self):
        html = self.html()

        assert '<optgroup label="Components">' in html and '<optgroup label="Files">' in html and 'id="blast-pick"' in html
        data = json.loads(re.search(r'<script type="application/json" id="blast-data">(.*?)</script>', html, re.S).group(1))
        assert len(data["files"]) == 4

    def test_sentence_counts_blind_spots(self):
        assert "Built from static imports. 2 places that load code at run time are not in this graph (see Gaps)." in self.html()

    def test_without_a_graph_the_sentence_changes(self):
        c = ctx({"graph": []})

        html = measured.body("change.blast-radius", c, Refs())

        assert "No import graph was extracted, so only co-changing files are shown." in html
