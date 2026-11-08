import checks

FLAGS = "Stale feature flags and unused routes are not detected for Python."


def gaps(extract):
    return [(g["report"], g["statement"]) for g in checks.validate({}, extract)["gaps"] if g["statement"] == FLAGS]


class TestStaleFlagsGap:
    def test_python_extraction_adds_the_fixed_item_for_the_change_report(self):
        assert gaps({"graph": [{"kind": "module", "path": "a.py", "module": "a"}]}) == [("change", FLAGS)]

    def test_no_python_graph_adds_nothing(self):
        assert gaps({"dead": []}) == []


JS = {"kind": "module", "path": "src/a.ts", "module": "src/a", "language": "js"}
PY = {"kind": "module", "path": "a.py", "module": "a"}
JS_FLAGS = "Stale feature flags and unused routes are not detected for JavaScript or TypeScript."


def statements(extract):
    return [g["statement"] for g in checks.validate({}, extract)["gaps"]]


class TestJavaScriptGaps:
    def test_the_python_item_appears_only_with_a_python_module(self):
        assert FLAGS in statements({"graph": [PY]}) and FLAGS not in statements({"graph": [JS]})

    def test_the_javascript_item_appears_only_with_a_javascript_module(self):
        assert JS_FLAGS in statements({"graph": [JS]}) and JS_FLAGS not in statements({"graph": [PY]})

    def test_a_mixed_repository_gets_both_items_once(self):
        got = statements({"graph": [JS, PY]})

        assert got.count(FLAGS) == 1 and got.count(JS_FLAGS) == 1

    def test_a_manifest_naming_koa_gives_the_framework_item_for_the_entry_report(self):
        note = {"kind": "js-note", "path": "package.json", "note": "framework", "name": "Koa"}

        found = [g for g in checks.validate({}, {"graph": [JS, note]})["gaps"] if "Koa" in g["statement"]]

        assert [(g["report"], g["statement"], g["how_to_confirm"]) for g in found] == [
            ("entry", "Routes written for Koa are not detected, so check the entry points by hand.", "This is a known limit of this version of dossier.")]

    def test_a_bun_project_gives_the_not_installed_item_for_the_dossier_report(self):
        note = {"kind": "js-note", "path": "apps/w/package.json", "note": "bun", "name": "apps/w"}

        found = [g for g in checks.validate({}, {"graph": [JS, note]})["gaps"] if "Bun" in g["statement"]]

        assert [(g["report"], g["statement"]) for g in found] == [
            ("dossier", "The packages of apps/w were not installed, because dossier does not install from Bun lockfiles.")]

    def test_skipped_mts_and_cts_files_give_a_counted_item(self):
        note = {"kind": "js-note", "path": "a.mts", "note": "unscanned", "name": "3"}

        found = [g for g in checks.validate({}, {"graph": [JS, note]})["gaps"] if ".mts" in g["statement"]]

        assert [(g["statement"], g["how_to_confirm"]) for g in found] == [("3 .mts or .cts file(s) were not scanned by the pattern rules.", "Read these files by hand.")]

    def test_an_unresolved_public_api_gives_the_io_item(self):
        note = {"kind": "js-note", "path": "packages/lib/package.json", "note": "api", "name": "@s/lib|./x"}

        found = [g for g in checks.validate({}, {"graph": [JS, note]})["gaps"] if "public API" in g["statement"]]

        assert [(g["report"], g["statement"]) for g in found] == [("io", "The public API of @s/lib could not be fully worked out from ./x.")]

    def test_no_js_extract_adds_none_of_these(self):
        assert [s for s in statements({"graph": [PY]}) if "Routes written" in s or "Bun" in s or "public API" in s] == []
