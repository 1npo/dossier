import js_queries


def call(path, text, line=1):
    return {"path": path, "capture": "call.fn", "text": text, "start_line": line, "end_line": line, "start_col": 0}


def source(path, text):
    return {"path": path, "capture": "import.source", "text": f"'{text}'", "start_line": 1, "end_line": 1, "start_col": 7}


def decl(path, text, line=1, col=0):
    return {"path": path, "capture": "decl", "text": text, "start_line": line, "end_line": line, "start_col": col}


def one(path, matches, runner=lambda p: None):
    return js_queries.assemble_tests({path: matches}, runner)[0]


class TestByGrammar:
    def test_extensions_go_to_their_grammar(self):
        out = js_queries.by_grammar(["a.ts", "b.mts", "c.cts", "d.tsx", "e.js", "f.jsx", "g.mjs", "h.cjs", "i.json"])

        assert out == {"typescript": ["a.ts", "b.mts", "c.cts"], "tsx": ["d.tsx"], "javascript": ["e.js", "f.jsx", "g.mjs", "h.cjs"]}


class TestAssembleTestsCounts:
    def test_test_forms_count_as_tests(self):
        calls = [call("t.ts", n) for n in ("it", "test", "specify", "it.each", "test.only", "it.concurrent")]

        assert one("t.ts", calls)["tests"] == 6

    def test_describe_and_suite_forms_count_as_classes(self):
        calls = [call("t.ts", n) for n in ("describe", "suite", "describe.each", "test.describe", "test.describe.serial")]

        assert one("t.ts", calls)["classes"] == 5

    def test_skip_todo_fixme_and_old_forms_count_as_skips_not_tests(self):
        calls = [call("t.ts", n) for n in ("it.skip", "test.todo", "test.fixme", "xit", "xtest", "xdescribe", "describe.skip")]

        item = one("t.ts", calls)

        assert (item["skips"], item["tests"], item["classes"]) == (7, 0, 0)

    def test_failing_and_fails_count_as_xfails(self):
        item = one("t.ts", [call("t.ts", "it.failing"), call("t.ts", "test.fails")])

        assert item["xfails"] == 2

    def test_mock_helpers_are_counted(self):
        calls = [call("t.ts", n) for n in ("jest.mock", "jest.fn", "vi.spyOn", "sinon.stub", "setupServer", "mockDeep", "console.log")]

        assert one("t.ts", calls)["mocks"] == 6

    def test_hooks_and_extend_are_fixtures(self):
        calls = [call("t.ts", n) for n in ("beforeAll", "beforeEach", "afterAll", "afterEach", "test.extend", "test.beforeEach")]

        assert one("t.ts", calls)["fixtures"] == 6

    def test_the_outer_call_of_a_curried_each_is_not_counted_twice(self):
        calls = [call("t.ts", "it.each"), call("t.ts", "it.each([1, 2])")]

        assert one("t.ts", calls)["tests"] == 1


class TestAssembleTestsFramework:
    def test_playwright_import_wins_and_makes_the_file_e2e(self):
        item = one("a.spec.ts", [source("a.spec.ts", "@playwright/test")])

        assert (item["framework"], item["test_kind"]) == ("playwright", "e2e")

    def test_vitest_and_node_test_imports(self):
        assert one("a.test.ts", [source("a.test.ts", "vitest")])["framework"] == "vitest"
        assert one("a.test.ts", [source("a.test.ts", "node:test")])["framework"] == "node:test"

    def test_cypress_folder_names_cypress(self):
        item = one("cypress/e2e/a.cy.ts", [])

        assert (item["framework"], item["test_kind"]) == ("cypress", "e2e")

    def test_the_configured_runner_is_the_fallback(self):
        assert one("tests/a.test.ts", [], lambda p: "jest")["framework"] == "jest"

    def test_no_import_and_no_config_is_unknown(self):
        assert one("tests/a.test.ts", [])["framework"] == "unknown"

    def test_integration_segment_makes_integration(self):
        assert one("tests/integration/a.test.ts", [], lambda p: "jest")["test_kind"] == "integration"

    def test_plain_files_are_unit(self):
        assert one("tests/a.test.ts", [], lambda p: "jest")["test_kind"] == "unit"


class TestAssembleState:
    def test_let_is_state_whether_or_not_exported(self):
        out = js_queries.assemble_state([decl("s.ts", "let current = null", 3, col=7), decl("s.ts", "let n = 0", 5)])

        assert [(i["name"], i["rule"]) for i in out] == [("current", "dossier.js.state.module-mutable"), ("n", "dossier.js.state.module-mutable")]

    def test_const_map_set_and_empty_containers_are_state(self):
        out = js_queries.assemble_state([decl("s.ts", "const cache = new Map()", 1), decl("s.ts", "const seen = new Set<string>()", 2),
                                         decl("s.ts", "const items: Item[] = []", 3), decl("s.ts", "const reg = {}", 4)])

        assert [i["name"] for i in out] == ["cache", "seen", "items", "reg"]

    def test_filled_object_constants_and_all_capitals_are_not_state(self):
        out = js_queries.assemble_state([decl("s.ts", "const NAMES = {a: 1}", 1), decl("s.ts", "const LIMITS = new Map(entries)", 2)])

        assert out == []

    def test_all_capitals_with_an_empty_value_stays(self):
        out = js_queries.assemble_state([decl("s.ts", "const CART = {}", 1)])

        assert [i["name"] for i in out] == ["CART"]

    def test_nested_declarations_are_ignored(self):
        assert js_queries.assemble_state([decl("s.ts", "let x = 1", 4, col=2)]) == []


FILES = {"jest.config.ts": "export default { coverageThreshold: { global: { branches: 70, lines: 80 } }, testMatch: ['**/*.test.ts'] };",
         "packages/web/vite.config.ts": "export default { test: { environment: 'jsdom' } }",
         "packages/api/vite.config.ts": "export default { plugins: [] }",
         "package.json": '{"jest": {"verbose": true}}', ".c8rc.json": '{"lines": 90}', "playwright.config.ts": "export default {}"}


class TestTestConfigs:
    def _configs(self):
        return js_queries.test_configs(sorted(FILES), FILES.get)

    def test_each_config_file_gives_an_item_with_its_tool(self):
        got = {(c["path"], c["tool"]) for c in self._configs()}

        assert got == {("jest.config.ts", "jest"), ("packages/web/vite.config.ts", "vitest"), ("package.json", "jest"),
                       (".c8rc.json", "c8"), ("playwright.config.ts", "playwright")}

    def test_jest_threshold_is_the_smallest_number_and_test_match_is_kept(self):
        jest = next(c for c in self._configs() if c["path"] == "jest.config.ts")

        assert jest["settings"] == {"coverage_threshold": 70, "test_match": "['**/*.test.ts']"}

    def test_c8_threshold_comes_from_the_whole_file(self):
        c8 = next(c for c in self._configs() if c["tool"] == "c8")

        assert c8["settings"] == {"coverage_threshold": 90}


class TestRunnerOf:
    def test_nearest_folder_wins_and_vitest_beats_jest_in_one_folder(self):
        configs = [{"path": "jest.config.ts", "tool": "jest"}, {"path": "packages/web/vite.config.ts", "tool": "vitest"},
                   {"path": "packages/x/vitest.config.ts", "tool": "vitest"}, {"path": "packages/x/jest.config.js", "tool": "jest"}]
        find = js_queries.runner_of(configs)

        assert (find("tests/a.test.ts"), find("packages/web/src/a.test.ts"), find("packages/x/a.test.ts")) == ("jest", "vitest", "vitest")

    def test_no_config_gives_none(self):
        assert js_queries.runner_of([])("a.test.ts") is None
