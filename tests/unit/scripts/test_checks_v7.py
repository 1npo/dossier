import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent / "scripts"))
import checks  # noqa: E402
import checks_v7  # noqa: E402

MODULE = {"kind": "module", "path": "src/a.py", "module": "a", "package": "a", "is_package": False}


def hit(pattern, path, line):
    return {"id": f"bs-{path}{line}", "group": f"bsg-{pattern}{path}", "path": path, "line": line, "pattern": pattern,
            "rule": f"dossier.python.blindspot.{pattern}", "snippet": "x"}


def blind(*hits, graph=True):
    return {"blindspots": list(hits), "graph": [MODULE] if graph else []}


class TestV7:
    def test_two_hits_of_one_pattern_in_one_file_give_one_item_citing_the_first_line(self):
        _, _, gaps, counts = checks_v7.v7(blind(hit("dynamic-import", "src/a.py", 20), hit("dynamic-import", "src/a.py", 9)))

        assert gaps[0] == {"kind": "coverage", "report": "interactions", "how_to_confirm": checks_v7.CONFIRM,
                           "statement": "Static analysis may miss imports made at run time here: 2 place(s) in [[src/a.py:9]]."}
        assert counts == {"v7": 1}

    def test_two_files_give_two_items(self):
        _, _, gaps, _ = checks_v7.v7(blind(hit("pytest-fixtures", "tests/a.py", 1), hit("pytest-fixtures", "tests/b.py", 1)))

        assert [g["report"] for g in gaps[:2]] == ["behavior", "behavior"]
        assert len(gaps) == 3

    def test_runtime_configuration_item_appears_once_when_a_python_adapter_ran(self):
        _, _, gaps, _ = checks_v7.v7(blind())

        assert [g["statement"] for g in gaps] == [checks_v7.RUNTIME_CONFIG]

    def test_no_python_adapter_gives_no_runtime_configuration_item(self):
        _, _, gaps, _ = checks_v7.v7(blind(graph=False))

        assert gaps == []

    def test_statements_are_identical_across_runs_whatever_the_input_order(self):
        a = [hit("codegen", "x.py", 1), hit("feature-flag", "y.py", 2)]

        first = checks_v7.v7(blind(*a))[2]
        second = checks_v7.v7(blind(*reversed(a)))[2]

        assert first == second

    def test_validate_adds_the_items_and_never_an_error(self):
        res = checks.validate({}, blind(hit("codegen", "x.py", 1)))

        assert any("generated code" in g["statement"] for g in res["gaps"])
        assert [e for e in res["errors"] if e.startswith("V7")] == []


JS_IDS = ("dynamic-require", "barrel-reexport", "react-context", "hook-wiring", "string-route", "route-mount", "module-federation", "di-registration")
JS_MODULE = {"kind": "module", "path": "src/a.ts", "module": "src/a", "short": "a", "package": None, "is_package": False, "language": "js"}


class TestJavaScriptBlindSpots:
    def test_every_javascript_pattern_has_wording_and_a_report(self):
        for pattern in JS_IDS:
            assert pattern in checks_v7.BLIND_SPOTS

    def test_a_hit_of_each_new_pattern_gives_its_own_sentence_not_the_fallback(self):
        extract = {"blindspots": [hit(p, "src/a.ts", 1) for p in JS_IDS], "graph": [JS_MODULE]}

        _, _, gaps, _ = checks_v7.v7(extract)

        assert not [g for g in gaps if "code that the rule for this pattern points at" in g["statement"]]
        assert {g["report"] for g in gaps} == {"interactions", "entry"}

    def test_a_literal_dynamic_import_is_not_a_hit_so_it_gives_no_item(self):
        _, _, gaps, _ = checks_v7.v7({"blindspots": [], "graph": [JS_MODULE]})

        assert [g["statement"] for g in gaps] == [checks_v7.RUNTIME_CONFIG]
