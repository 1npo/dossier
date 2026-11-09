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


def cs_module(path):
    return {"kind": "module", "path": path, "module": path[:-3], "short": path.rsplit("/", 1)[-1][:-3], "language": "csharp"}


def cs_use(a, b):
    return {"kind": "import", "path": a, "paths": [b], "from": a[:-3], "to": b[:-3], "via": "type-use"}


class TestCSharpData:
    def csctx(self):
        extract = {"graph": [cs_module("src/Core/Order.cs"), cs_module("src/Core/Cart.cs"), cs_module("src/Api/Checkout.cs"),
                             cs_use("src/Core/Cart.cs", "src/Core/Order.cs"), cs_use("src/Api/Checkout.cs", "src/Core/Cart.cs")],
                   "tests": [{"kind": "test-file", "path": "tests/OrderTests.cs", "paths": ["src/Core/Order.cs"]}],
                   "history": [{"kind": "meta"}, {"kind": "pair", "a": "src/Core/Core.csproj", "b": "src/Core/Order.cs", "co_commits": 5, "share": 50, "path": "src/Core/Order.cs"}]}
        tree = {"src/Core/Order.cs", "src/Core/Cart.cs", "src/Api/Checkout.cs", "src/Core/Core.csproj", "src/Api/Index.razor", "tests/OrderTests.cs"}
        return {"extract": extract, "tree": tree, "catalog": [], "facts": {}}

    def test_the_blast_radius_of_a_type_holds_the_files_that_use_it_and_the_tests_that_name_it(self):
        d = measured_blast.data(self.csctx())
        i = d["files"].index("src/Core/Order.cs")

        assert {d["files"][j] for j in decode(d["dep"][i], len(d["files"]))} == {"src/Core/Cart.cs", "src/Api/Checkout.cs"}
        assert d["direct"][i] == 1 and [d["tests"][t] for t in d["ft"][i]] == ["tests/OrderTests.cs"]

    def test_a_project_file_has_co_change_rows_and_no_graph_row(self):
        d = measured_blast.data(self.csctx())

        assert "src/Core/Core.csproj" not in d["files"] and d["co"]["src/Core/Core.csproj"] == [["src/Core/Order.cs", 5]]

    def test_a_razor_file_is_in_no_graph_and_not_a_listed_file(self):
        d = measured_blast.data(self.csctx())

        assert "src/Api/Index.razor" not in d["files"] and all(f.endswith(".cs") for f in d["files"])
