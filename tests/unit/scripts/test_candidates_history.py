import candidates_history


def sym(path, name, descriptors):
    return {"kind": "def", "path": path, "name": name, "symbol": f"scip-typescript npm . . {descriptors}"}


def duplicates(symbols):
    extract = {"history": [{"kind": "meta"}], "symbols": symbols}

    return candidates_history.data("change", extract, {}, None, {"src/a.ts", "src/b.ts"})["Same name defined more than once"]


class TestSameNameDefinedMoreThanOnce:
    def test_a_top_level_name_defined_in_two_files_is_listed(self):
        symbols = [sym("src/a.ts", "load", "`src/a.ts`/load()."), sym("src/b.ts", "load", "`src/b.ts`/load().")]

        got = duplicates(symbols)

        assert got == ["load  in 2 files: src/a.ts, src/b.ts"]

    def test_object_keys_and_members_are_left_out(self):
        symbols = [sym("src/a.ts", "name", "`src/a.ts`/config.name."), sym("src/b.ts", "name", "`src/b.ts`/other.name."),
                   sym("src/a.ts", "render", "`src/a.ts`/A#render()."), sym("src/b.ts", "render", "`src/b.ts`/B#render().")]

        got = duplicates(symbols)

        assert got == []

    def test_local_symbols_are_left_out(self):
        symbols = [sym("src/a.ts", "i", "local 1"), sym("src/b.ts", "i", "local 2")]

        got = duplicates(symbols)

        assert got == []
