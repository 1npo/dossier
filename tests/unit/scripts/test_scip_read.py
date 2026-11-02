import scip_read

SYMBOL = "scip-python python pkg 1.0 pkg/a/f()."


def varint(n):
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out


def field(num, payload):
    """A length-delimited field (or a varint field when payload is an int)."""
    if isinstance(payload, int):
        return varint(num << 3) + varint(payload)
    if isinstance(payload, str):
        payload = payload.encode()
    return varint((num << 3) | 2) + varint(len(payload)) + payload


def packed(nums):
    return b"".join(varint(n) for n in nums)


def occurrence(rng, symbol, roles, enclosing=None, repeated=False):
    body = b"".join(field(1, n) for n in rng) if repeated else field(1, packed(rng))
    body += field(2, symbol) + field(3, roles)
    if enclosing:
        body += field(7, packed(enclosing))
    return body


def document(path, occurrences, symbols=()):
    body = field(1, path) + b"".join(field(2, o) for o in occurrences)
    for sym, name in symbols:
        body += field(3, field(1, sym) + field(5, 17) + field(6, name))
    return body


def index_bytes():
    meta = field(1, field(2, "scip-python"))
    doc_a = document("pkg/a.py", [occurrence([2, 4, 5], SYMBOL, 1, enclosing=[2, 0, 4, 10]), occurrence([5, 0, 1], "local 1", 1)],
                     symbols=[(SYMBOL, "f")])
    doc_b = document("pkg/b.py", [occurrence([0, 0, 1], SYMBOL, 8), occurrence([3, 0, 3, 1], SYMBOL, 8, repeated=True)])
    unknown = varint((99 << 3) | 1) + b"\x00" * 8 + field(100, "ignored")
    return field(1, meta) + field(2, doc_a) + unknown + field(2, doc_b) + varint(7 << 3) + varint(5)


class TestDecode:
    def test_documents_occurrences_and_symbols_are_read(self):
        got = scip_read.decode(index_bytes())

        a, b = got["documents"]
        assert (a["path"], b["path"]) == ("pkg/a.py", "pkg/b.py")
        assert a["occurrences"][0]["range"] == [2, 4, 2, 5] and a["occurrences"][0]["enclosing_range"] == [2, 0, 4, 10]
        assert a["symbols"] == [{"symbol": SYMBOL, "kind": 17, "display_name": "f"}]

    def test_ranges_may_be_packed_or_repeated_and_three_or_four_long(self):
        got = scip_read.decode(index_bytes())

        assert [o["range"] for o in got["documents"][1]["occurrences"]] == [[0, 0, 0, 1], [3, 0, 3, 1]]

    def test_unknown_fields_are_skipped(self):
        assert len(scip_read.decode(index_bytes())["documents"]) == 2

    def test_empty_input_gives_no_documents(self):
        assert scip_read.decode(b"") == {"documents": []}


class TestReduce:
    def test_one_definition_with_two_outside_references(self):
        items = scip_read.reduce(scip_read.decode(index_bytes()))

        defs = [i for i in items if i["kind"] == "def"]
        assert defs == [{"kind": "def", "path": "pkg/a.py", "line": 3, "end_line": 5, "name": "f", "symbol": SYMBOL,
                         "type": "function", "public": True, "refs": 2}]

    def test_one_ref_edge_counts_both_references(self):
        items = scip_read.reduce(scip_read.decode(index_bytes()))

        assert [i for i in items if i["kind"] == "ref-edge"] == [{"kind": "ref-edge", "path": "pkg/b.py", "paths": ["pkg/a.py"], "count": 2}]

    def test_local_symbols_are_skipped(self):
        items = scip_read.reduce(scip_read.decode(index_bytes()))

        assert all(not i.get("symbol", "").startswith("local") for i in items)

    def test_references_inside_the_defining_file_make_no_edge(self):
        doc = document("pkg/a.py", [occurrence([0, 0, 1], SYMBOL, 1), occurrence([2, 0, 1], SYMBOL, 8)])

        items = scip_read.reduce(scip_read.decode(field(2, doc)))

        assert [i["kind"] for i in items] == ["def"] and items[0]["refs"] == 0


class TestDescriptorType:
    def test_each_suffix_gives_its_type(self):
        got = [scip_read.descriptor_type(f"scip-python python pkg 1.0 {d}") for d in ("pkg/A#", "pkg/A#m().", "pkg/a/f().", "pkg/a/X.", "pkg/a/")]

        assert got == ["class", "method", "function", "variable", "module"]


class TestPublic:
    def reduce_one(self, descriptors):
        symbol = f"scip-python python pkg 1.0 {descriptors}"
        doc = document("pkg/a.py", [occurrence([0, 0, 1], symbol, 1)])
        return scip_read.reduce(scip_read.decode(field(2, doc)))[0]

    def test_underscore_part_is_not_public(self):
        assert self.reduce_one("pkg/a/_helper().")["public"] is False

    def test_class_member_is_public(self):
        assert self.reduce_one("pkg/A#m().")["public"] is True

    def test_member_of_a_nested_class_is_not_public(self):
        assert self.reduce_one("pkg/A#B#c.")["public"] is False
