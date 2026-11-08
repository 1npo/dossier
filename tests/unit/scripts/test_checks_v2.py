import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent / "scripts"))
import checks  # noqa: E402

CODE = "def load_config(path):\n    return parse(path)\n\nclass Store:\n    def save(self):\n        pass\n\nimport os.path\n"
BLOBS = {"src/app.py": CODE.encode(), "README.md": b"hello"}


def reports(text, cite, rid="entry", **kw):
    node = {"type": "text", "text": text, "conf": "confirmed", "cite": cite, **kw}
    return {rid: {"cards": [{"card": f"{rid}.catalog", "blocks": [node]}]}}


def run(make_cites, text, cite, dirs=("src",)):
    cites = make_cites(BLOBS, dirs)
    return checks.v2(reports(text, cite), cites, {"src/app.py", "README.md"})


class TestV2:
    def test_span_inside_the_cited_lines_passes(self, make_cites):
        _, warnings, gaps, counts = run(make_cites, "It calls `load_config`.", ["src/app.py:1-2"])

        assert (warnings, gaps, counts) == ([], [], {"v2": 0})

    def test_span_outside_the_cited_range_warns_with_one_gap_item(self, make_cites):
        _, warnings, gaps, counts = run(make_cites, "It uses `Store`.", ["src/app.py:1-2"])

        assert warnings == ["V2: entry 'It uses `Store`.': Store does not appear in the code it cites (src/app.py:1-2)."]
        assert gaps == [{"kind": "inference", "report": "entry", "cite": ["src/app.py:1-2"],
                         "statement": "A statement in Entry points names `Store`, which does not appear in the code it cites.",
                         "how_to_confirm": "Check the citation's line range, or the name."}]
        assert counts == {"v2": 1}

    def test_dotted_name_passes_on_its_last_part(self, make_cites):
        _, warnings, _, _ = run(make_cites, "It uses `app.Store.save`.", ["src/app.py:4-6"])

        assert warnings == []

    def test_call_form_passes_on_the_bare_name(self, make_cites):
        _, warnings, _, _ = run(make_cites, "It runs `parse()`.", ["src/app.py:1-2"])

        assert warnings == []

    def test_keywords_builtins_short_words_and_paths_are_skipped(self, make_cites):
        text = "Uses `class`, `print`, `get`, `True`, `none` and `README.md`."

        _, warnings, _, _ = run(make_cites, text, ["src/app.py:1-2"])

        assert warnings == []

    def test_directory_or_facts_citation_is_not_checked(self, make_cites):
        _, w1, _, _ = run(make_cites, "It uses `Missing`.", ["src"])
        _, w2, _, _ = run(make_cites, "It uses `Missing`.", ["facts:languages"])

        assert (w1, w2) == ([], [])

    def test_whole_file_citation_searches_the_whole_file(self, make_cites):
        _, warnings, _, _ = run(make_cites, "It has `Store`.", ["src/app.py"])

        assert warnings == []

    def test_table_cells_are_checked(self, make_cites):
        reps = {"entry": {"cards": [{"card": "entry.catalog", "blocks": [{"type": "table", "columns": ["A", "B"], "rows": [
            {"cells": ["x", "`Nowhere`"], "conf": "confirmed", "cite": ["src/app.py:1-2"]}]}]}]}}

        _, warnings, _, _ = checks.v2(reps, make_cites(BLOBS, ("src",)), set())

        assert len(warnings) == 1 and "Nowhere" in warnings[0]


def recipes(conf="inferred", example="It followed the layout.", cite=("src/app.py:1",), recipe="Add a migration"):
    entry = {"recipe": recipe, "fields": {"files_to_touch": "1. a\n2. b", "worked_example": example}, "conf": conf, "cite": list(cite)}
    return {"conventions": {"cards": [{"card": "conventions.recipes", "entries": [entry]}]}}


class TestV2Recipes:
    def test_a_recipe_with_no_commit_warns_and_gives_one_inference_item(self):
        warnings, gaps, count = checks.v2_recipes(recipes())

        assert warnings == ["V2: Recipes, Add a migration: the worked example cites no commit."]
        assert gaps == [{"kind": "inference", "report": "conventions", "cite": ["src/app.py:1"],
                         "statement": "The recipe 'Add a migration' has a worked example that cites no commit.",
                         "how_to_confirm": "Find the commit that did the same thing (git log -S) and cite it, or say it is unknown."}]
        assert count == 1

    def test_a_commit_in_the_entry_citations_passes(self):
        assert checks.v2_recipes(recipes(cite=("src/app.py:1", "commit:1a2b3c4d5e6f")))[0] == []

    def test_a_commit_cited_inline_in_the_example_passes(self):
        assert checks.v2_recipes(recipes(example="Commit [[commit:1a2b3c4d5e6f]] added the table."))[0] == []

    def test_an_example_marked_unknown_is_not_flagged(self):
        assert checks.v2_recipes(recipes(conf="unknown", example="No commit did this."))[0] == []

    def test_a_confirmed_recipe_is_flagged_too(self):
        assert len(checks.v2_recipes(recipes(conf="confirmed"))[0]) == 1

    def test_reports_without_recipes_are_fine(self):
        assert checks.v2_recipes({}) == ([], [], 0)

    def test_validate_returns_the_warning_and_the_count(self):
        res = checks.validate(recipes(), {}, None, {})

        assert any("worked example cites no commit" in w for w in res["warnings"])
        assert res["counts"]["v2_recipes"] == 1


MODULES = {"cannalerts", "cannalerts.alerts", "cannalerts.alerts.state", "cannalerts.menus"}


def run_with_modules(make_cites, text, cite, modules=MODULES):
    return checks.v2(reports(text, cite), make_cites(BLOBS, ("src",)), {"src/app.py", "README.md"}, modules)


class TestV2FileAndModuleNames:
    def test_a_bare_file_name_is_not_a_code_identifier(self, make_cites):
        _, warnings, _, _ = run_with_modules(make_cites, "Both `cli.py` and `models.py` hold it.", ["src/app.py:1-2"])

        assert warnings == []

    def test_a_module_name_by_its_dotted_suffix_is_skipped(self, make_cites):
        _, warnings, _, _ = run_with_modules(make_cites, "State lives in `alerts.state`.", ["src/app.py:1-2"])

        assert warnings == []

    def test_a_full_module_name_is_skipped(self, make_cites):
        _, warnings, _, _ = run_with_modules(make_cites, "Imports `cannalerts.menus`.", ["src/app.py:1-2"])

        assert warnings == []

    def test_a_module_dot_name_passes_when_the_name_is_in_the_cited_text(self, make_cites):
        _, warnings, _, _ = run_with_modules(make_cites, "It calls `menus.load_config`.", ["src/app.py:1-2"])

        assert warnings == []

    def test_a_module_dot_name_warns_when_the_name_is_not_in_the_cited_text(self, make_cites):
        _, warnings, _, _ = run_with_modules(make_cites, "It calls `menus.scrape_cached`.", ["src/app.py:1-2"])

        assert len(warnings) == 1 and "menus.scrape_cached" in warnings[0]

    def test_a_class_name_missing_from_the_cited_text_still_warns(self, make_cites):
        _, warnings, _, _ = run_with_modules(make_cites, "It uses `FetchClient`.", ["src/app.py:1-2"])

        assert len(warnings) == 1

    def test_a_longer_dotted_name_is_not_a_suffix_match(self, make_cites):
        _, warnings, _, _ = run_with_modules(make_cites, "It uses `other.alerts.state`.", ["src/app.py:1-2"])

        assert len(warnings) == 1

    def test_validate_passes_the_modules_of_the_import_graph(self, make_cites):
        extract = {"graph": [{"kind": "module", "module": "cannalerts.alerts.state", "path": "src/a.py"}]}

        res = checks.validate(reports("State lives in `alerts.state`.", ["src/app.py:1-2"]), extract, make_cites(BLOBS, ("src",)), {})

        assert not [w for w in res["warnings"] if w.startswith("V2")]


class TestV2JavaScript:
    def go(self, make_cites, text, **kw):
        return checks.v2(reports(text, ["src/app.py:1-2"]), make_cites(BLOBS, ("src",)), {"src/app.py", "README.md"}, **kw)

    def test_a_short_module_name_is_not_looked_for_in_the_code(self, make_cites):
        _, warnings, _, _ = self.go(make_cites, "State lives in `routes`.", modules=checks.module_inputs([
            {"kind": "module", "module": "src/routes/index", "short": "routes", "language": "js"}])[0])

        assert warnings == []

    def test_module_inputs_adds_each_short_name_and_flags_javascript(self):
        names, js = checks.module_inputs([{"kind": "module", "module": "src/a", "short": "a", "language": "js"},
                                          {"kind": "import", "from": "x", "to": "y"}])

        assert {"src/a", "a"} <= names and js is True

    def test_module_inputs_for_python_is_unchanged(self):
        names, js = checks.module_inputs([{"kind": "module", "module": "app.cli", "package": "app"}])

        assert names == {"app.cli"} and js is False

    def test_javascript_words_are_skipped_only_for_a_javascript_repository(self, make_cites):
        _, plain, _, _ = self.go(make_cites, "It returns a `Promise`.")
        _, js, _, _ = self.go(make_cites, "It returns a `Promise`.", js=True)

        assert len(plain) == 1 and js == []
