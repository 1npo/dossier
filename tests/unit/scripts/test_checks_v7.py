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


CS_IDS = ("di-registration", "di-scan", "di-resolution", "reflection", "route-convention", "conventional-route", "mvc-filter", "mediator-handler",
          "source-generator", "partial-class", "codegen", "feature-flag", "string-route", "route-mount")
CS_MODULE = {"kind": "module", "path": "src/A.cs", "module": "src/A", "short": "A", "language": "csharp", "generated": False, "complexity": 0}


def cs_extract(*notes, hits=(), module=True):
    return {"blindspots": list(hits), "graph": ([CS_MODULE] if module else []) + [{"kind": "cs-note", "path": "x.cs", **n} for n in notes]}


class TestCSharpBlindSpots:
    def test_every_csharp_pattern_has_wording_and_a_report(self):
        for pattern in CS_IDS:
            assert pattern in checks_v7.BLIND_SPOTS

    def test_a_hit_of_each_pattern_gives_its_own_sentence_not_the_fallback(self):
        _, _, gaps, _ = checks_v7.v7(cs_extract(hits=[hit(p, "src/A.cs", 1) for p in CS_IDS]))

        assert not [g for g in gaps if "code that the rule for this pattern points at" in g["statement"]]
        assert {g["report"] for g in gaps} == {"interactions", "entry", "components"}

    def test_one_item_per_pattern_and_file(self):
        _, _, gaps, counts = checks_v7.v7(cs_extract(hits=[hit("di-scan", "src/A.cs", 9), hit("di-scan", "src/A.cs", 3), hit("di-scan", "src/B.cs", 1)]))

        assert counts == {"v7": 2}
        assert gaps[0]["statement"] == "Static analysis may miss services registered by scanning assemblies, so which classes are used is decided at run time here: 2 place(s) in [[src/A.cs:3]]."

    def test_the_new_wording_does_not_change_the_old_wording(self):
        assert checks_v7.BLIND_SPOTS["dynamic-import"] == ("imports made at run time", "interactions")
        assert checks_v7.BLIND_SPOTS["di-registration"] == ("objects built and passed in by a dependency injection container", "interactions")


class TestCSharpCoverage:
    def test_a_csharp_module_gives_the_stale_flags_and_file_link_items_only_for_csharp(self):
        got = checks_v7.cs_coverage(cs_extract())

        assert [(g["report"], g["statement"]) for g in got] == [("change", "Stale feature flags and unused routes are not detected for C#."), ("interactions", checks_v7.CS_LINKS)]

    def test_no_csharp_module_gives_nothing(self):
        assert checks_v7.cs_coverage(cs_extract(module=False)) == []
        assert checks_v7.cs_coverage({"graph": [MODULE]}) == []
        assert checks_v7.cs_coverage({"graph": [JS_MODULE]}) == []

    def test_each_note_gives_its_fixed_sentence(self):
        notes = [{"note": "framework", "name": "FastEndpoints"}, {"note": "no-lock", "name": "Shop.Api"}, {"note": "sdk", "name": "The .NET SDK is not installed."},
                 {"note": "razor", "name": "2"}, {"note": "generator", "name": "Riok.Mapperly|src/A/A.csproj"}, {"note": "ambiguous-name", "name": "3"},
                 {"note": "ambiguous-symbol", "name": "4"}, {"note": "unindexed", "name": "5"}, {"note": "msbuild", "name": "Failure: x"},
                 {"note": "api", "name": "Shop.Core"}, {"note": "dead", "name": "."}]

        got = {g["statement"]: g for g in checks_v7.cs_coverage(cs_extract(*notes, module=False))}

        assert set(got) == {
            "Routes and handlers written for FastEndpoints are not detected, so check the entry points by hand.",
            "The packages of Shop.Api were not installed, because it has no packages.lock.json and dossier installs only from lock files.",
            "The C# tools that need the .NET SDK did not run: The .NET SDK is not installed.",
            "2 Razor or Blazor file(s) were not read by the reference index or the pattern rules; only their @page routes were found.",
            "Code generated at build time by Riok.Mapperly in src/A/A.csproj is not in the repository, and static analysis did not read it.",
            "3 type name(s) are declared more than once in visible namespaces, so uses of them were not linked between files.",
            "4 name(s) were given the same identity by scip-dotnet, so references to them were not counted.",
            "5 C# file(s) are not in the scip-dotnet index, so references from and to them were not counted.",
            "scip-dotnet could not load every project: Failure: x",
            "The public API of Shop.Core could not be fully worked out.",
            checks_v7.CS_DEAD}
        assert got["The public API of Shop.Core could not be fully worked out."]["report"] == "io"
        assert got["5 C# file(s) are not in the scip-dotnet index, so references from and to them were not counted."]["how_to_confirm"] == "Read these files by hand."

    def test_a_python_only_and_a_js_only_extract_give_the_same_items_as_before(self):
        py = [g["statement"] for g in checks.validate({}, {"blindspots": [], "graph": [MODULE]})["gaps"]]
        js = [g["statement"] for g in checks.validate({}, {"blindspots": [], "graph": [JS_MODULE]})["gaps"]]
        assert not any("C#" in s or "type names" in s for s in py + js)

    def test_validate_adds_the_csharp_items(self):
        gaps = checks.validate({}, cs_extract({"note": "framework", "name": "Carter"}))["gaps"]

        assert any("written for Carter" in g["statement"] for g in gaps) and any(g["statement"] == checks_v7.CS_LINKS for g in gaps)
