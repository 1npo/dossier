import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent / "scripts"))
import checks  # noqa: E402

TREE = {"src/app/a.py", "src/app/api/b.py", "src/app/api/c.py", "scripts/run.sh", "docs/x.md", "uv.lock", "README.md", "src/other/z.py"}


def catalog(*rows, unassigned=None):
    entry = {"card": "components.catalog", "blocks": [{"type": "table", "columns": ["Component", "Paths"], "rows": [
        {"cells": [n, p], "conf": "confirmed", "cite": ["a"]} for n, p in rows]}]}
    if unassigned is not None:
        entry["unassigned"] = unassigned
    return entry


def reports(cat, detail=None):
    cards = [cat] + ([detail] if detail else [])
    return {"components": {"cards": cards}}


def detail(*names):
    return {"card": "components.detail", "entries": [{"component": n, "fields": {}} for n in names]}


class TestParsePaths:
    def test_splits_on_commas_and_newlines_and_strips_backticks(self):
        assert checks.parse_paths("`src/a/`, x.py\n`b/*.sh`") == ["src/a/", "x.py", "b/*.sh"]

    def test_citation_becomes_its_path(self):
        assert checks.parse_paths("[[src/a.py:1-5|a.py]]") == ["src/a.py"]


class TestBestComponent:
    ROWS = [{"name": "App", "paths": ["src/app/"]}, {"name": "Api", "paths": ["src/app/api/"]}, {"name": "Glob", "paths": ["src/app/api/*.py"]},
            {"name": "One", "paths": ["src/app/api/b.py"]}]

    def test_deeper_directory_beats_shallower(self):
        assert checks.best_component("src/app/a.py", self.ROWS[:2]) == ("App", [])
        assert checks.best_component("src/app/api/c.py", self.ROWS[:2]) == ("Api", [])

    def test_file_beats_glob_beats_directory(self):
        assert checks.best_component("src/app/api/c.py", self.ROWS[:3])[0] == "Glob"
        assert checks.best_component("src/app/api/b.py", self.ROWS)[0] == "One"

    def test_equal_matches_are_a_tie(self):
        rows = [{"name": "A", "paths": ["src/x/"]}, {"name": "B", "paths": ["src/x/"]}]

        assert checks.best_component("src/x/f.py", rows) == ("A", ["B"])


class TestV4:
    def test_every_file_covered_passes_and_noise_is_not_counted(self):
        reps = reports(catalog(("App", "`src/app/`"), ("Other", "src/other/"), ("Scripts", "scripts/*.sh"),),
                       detail("App", "Other", "Scripts"))

        errors, warnings, gaps, counts = checks.v4(reps, TREE)

        assert errors == [] and warnings == [] and gaps == [] and counts == {"v4": 0}

    def test_tie_between_components_errors(self):
        reps = reports(catalog(("A", "src/app/"), ("B", "src/app/"), ("O", "src/other/"), ("S", "scripts/")), detail("A", "B", "O", "S"))

        errors, _, _, _ = checks.v4(reps, TREE)

        assert "V4: src/app/a.py belongs to both A and B." in errors

    def test_unmatched_files_error_and_list_at_most_five(self):
        tree = {f"pkg/m{i}.py" for i in range(7)}
        reps = reports(catalog(("X", "other/")))

        errors, _, _, _ = checks.v4(reps, tree)

        assert errors == ["V4: 7 source files belong to no component and are not listed as unassigned, for example "
                          "pkg/m0.py, pkg/m1.py, pkg/m2.py, pkg/m3.py, pkg/m4.py and 2 more."]

    def test_unassigned_covers_files_and_adds_one_gap_item_per_entry(self):
        reps = reports(catalog(("App", "src/app/"), ("S", "scripts/*.sh"), unassigned=[{"paths": "src/other/", "reason": "Scratch code."}]), detail("App", "S"))

        errors, _, gaps, _ = checks.v4(reps, TREE)

        assert errors == []
        assert gaps == [{"kind": "coverage", "report": "components", "statement": "1 source file(s) in src/other/ belong to no component: Scratch code.",
                         "how_to_confirm": "Check that these files really are not part of any component."}]

    def test_missing_detail_entry_errors_and_extra_one_warns(self):
        reps = reports(catalog(("App", "src/app/"), ("Other", "src/other/"), ("S", "scripts/")), detail("app", "`Other`", "Ghost"))

        errors, warnings, _, _ = checks.v4(reps, TREE)

        assert errors == ["V4: the component S has no entry in Component details."]
        assert warnings == ["V4: Component details has an entry for Ghost, which is not in the Component catalog."]

    def test_na_and_pending_catalogs_skip_the_check(self):
        for entry in ({"card": "components.catalog", "pending": True}, {"card": "components.catalog", "na": "No code.", "cite": ["a"]}):
            assert checks.v4(reports(entry), TREE) == ([], [], [], {"v4": 0})

    def test_validate_runs_v4_when_a_tree_is_available(self):
        class Cites:
            def tree(self):
                return TREE, set()

        res = checks.validate(reports(catalog(("App", "src/app/"))), {"graph": []}, Cites())

        assert res["counts"]["v4"] == 1 and any(e.startswith("V4:") for e in res["errors"])

    def test_validate_skips_v4_without_extractor_output(self):
        class Cites:
            def tree(self):
                return TREE, set()

        res = checks.validate(reports(catalog(("App", "src/app/"))), {}, Cites())

        assert res["errors"] == []
