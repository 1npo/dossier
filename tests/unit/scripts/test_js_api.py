import js_api

LIB_FILES = {"packages/lib/package.json", "packages/lib/src/index.ts", "packages/lib/src/math.ts", "packages/lib/src/utils/fmt.ts",
             "packages/lib/src/utils/deep/x.ts", "packages/lib/src/internal/x.ts", "packages/lib/src/types.d.ts"}
OPTIONS = {"outDir": "dist", "rootDir": "src"}


def pkg(manifest, folder="packages/lib"):
    return {"dir": folder, "manifest": {"name": "@s/lib", **manifest}}


def rows(manifest, files=LIB_FILES, options=OPTIONS, folder="packages/lib"):
    return js_api.entries(pkg(manifest, folder), files, options)


def by_sub(result):
    return {r["subpath"]: r for r in result}


class TestEntries:
    def test_exports_beat_main(self):
        got = rows({"main": "./src/math.ts", "exports": {".": "./src/index.ts"}})

        assert [(r["subpath"], r["file"]) for r in got] == [(".", "packages/lib/src/index.ts")]

    def test_nested_conditions_give_one_row_for_the_first_target_that_maps(self):
        got = rows({"exports": {".": {"types": "./dist/index.d.ts", "import": {"node": "./dist/index.mjs", "default": "./dist/index.js"}}}})

        assert [(r["subpath"], r["file"]) for r in got] == [(".", "packages/lib/src/index.ts")]

    def test_package_json_and_other_non_code_targets_are_skipped(self):
        got = rows({"exports": {".": "./src/index.ts", "./package.json": "./package.json", "./style.css": "./dist/s.css"}})

        assert [r["subpath"] for r in got] == ["."]

    def test_a_null_target_is_excluded(self):
        got = rows({"exports": {".": "./src/index.ts", "./internal/*": None}})

        assert [r["subpath"] for r in got] == ["."]

    def test_a_wildcard_expands_over_source_files_across_folders_without_declarations(self):
        got = rows({"exports": {"./utils/*": "./src/utils/*.ts"}})

        assert [(r["subpath"], r["file"]) for r in got] == [("./utils/deep/x", "packages/lib/src/utils/deep/x.ts"), ("./utils/fmt", "packages/lib/src/utils/fmt.ts")]

    def test_a_wildcard_over_built_files_maps_back_to_sources_through_tsconfig_paths_or_src(self):
        files = {"p/package.json", "p/src/index.ts", "p/src/middleware.ts", "p/src/middleware/persist.ts"}
        exports = {"./*": {"import": {"default": "./esm/*.mjs"}, "default": {"default": "./*.js"}}}

        got = js_api.entries({"dir": "p", "manifest": {"name": "z", "exports": exports}}, files, {"paths": {"z/*": ["./src/*.ts"]}})

        assert [r["subpath"] for r in got] == ["./index", "./middleware", "./middleware/persist"]

    def test_a_wildcard_skips_files_of_a_nested_package(self):
        files = {"package.json", "x.js", "examples/demo/package.json", "examples/demo/y.js"}

        got = js_api.entries({"dir": "", "manifest": {"name": "z", "exports": {"./*": "./*.js"}}}, files, {})

        assert [r["subpath"] for r in got] == ["./x"]

    def test_a_wildcard_over_built_files_maps_back_to_sources(self):
        got = rows({"exports": {"./u/*": "./dist/utils/*.js"}})

        assert [r["subpath"] for r in got] == ["./u/deep/x", "./u/fmt"]

    def test_a_built_target_maps_through_out_dir_and_root_dir(self):
        got = rows({"exports": {".": "./dist/math.js"}})

        assert got[0]["file"] == "packages/lib/src/math.ts"

    def test_a_tsconfig_paths_entry_for_the_package_name_names_the_source(self):
        got = rows({"exports": {".": "./dist/index.js"}}, options={"paths": {"@s/lib": ["./src/math.ts"]}})

        assert got[0]["file"] == "packages/lib/src/math.ts"

    def test_the_same_relative_path_under_src_is_the_last_resort(self):
        got = rows({"exports": {".": "./build/index.js"}}, options={})

        assert got[0]["file"] == "packages/lib/src/index.ts"

    def test_an_unmappable_target_is_unresolved(self):
        got = rows({"exports": {".": "./dist/nowhere.js"}}, options={})

        assert (got[0]["file"], got[0]["resolved"]) == (None, False)

    def test_main_then_module_then_types_without_exports(self):
        got = rows({"main": "./dist/nowhere.js", "module": "./dist/math.js"})

        assert [(r["subpath"], r["file"]) for r in got] == [(".", "packages/lib/src/math.ts")]

    def test_private_sets_the_audience_either_way(self):
        assert rows({"private": True, "main": "./src/index.ts"})[0]["audience"] == "marked private"
        assert rows({"main": "./src/index.ts"})[0]["audience"] == "not marked private"

    def test_no_fields_gives_no_rows(self):
        assert rows({"name": "x", "private": True}) == []

    def test_a_package_at_the_repository_root_maps_paths_without_a_folder(self):
        got = js_api.entries({"dir": "", "manifest": {"name": "z", "main": "./dist/index.js"}}, {"src/index.ts"}, OPTIONS)

        assert got[0]["file"] == "src/index.ts"


class TestReadTsconfig:
    def test_comments_and_trailing_commas_are_tolerated(self):
        text = '{\n // c\n "compilerOptions": {"outDir": "dist", /* x */ "rootDir": "src",},\n}'

        assert js_api.read_tsconfig(lambda p: text, "t.json") == {"outDir": "dist", "rootDir": "src"}

    def test_a_missing_or_broken_file_gives_none(self):
        assert js_api.read_tsconfig(lambda p: None, "t.json") is None
        assert js_api.read_tsconfig(lambda p: "{", "t.json") is None

    def test_slashes_inside_strings_are_kept(self):
        assert js_api.read_tsconfig(lambda p: '{"compilerOptions": {"outDir": "a//b"}}', "t") == {"outDir": "a//b"}


class TestItems:
    ENTRY = {"package": "@s/lib", "subpath": ".", "file": "p/src/index.ts", "resolved": True, "audience": "not marked private"}

    def test_api_rows_become_public_api_symbols(self):
        api = [{"entry": "p/src/index.ts", "subpath": ".", "name": "deep", "kind": "function", "path": "p/src/deep.ts", "line": 1},
               {"entry": "p/src/index.ts", "subpath": ".", "name": "ext", "kind": "type", "path": None, "line": 4, "external": "zod"}]

        symbols, notes = js_api.items([self.ENTRY], api, [])

        assert [(s["name"], s["path"], s["package"], s["external"]) for s in symbols] == [("deep", "p/src/deep.ts", "@s/lib", None), ("ext", "p/src/index.ts", "@s/lib", "zod")]
        assert notes == []

    def test_unresolved_entries_and_names_become_notes_once(self):
        bad = {**self.ENTRY, "subpath": "./x", "file": None, "resolved": False}
        unresolved = [{"entry": "p/src/index.ts", "subpath": ".", "specifier": "missing"}]

        _, notes = js_api.items([self.ENTRY, bad], [], unresolved + unresolved)

        assert sorted(n["name"] for n in notes) == ["@s/lib|.", "@s/lib|./x"]
