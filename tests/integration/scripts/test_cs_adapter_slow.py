"""The test of record for the C# adapter (plan 011, M5-21): one real extraction of the fixture repository, then every output checked.

`Shop.Core` is the only project with a lock file, so it is the only one restored (offline). The other projects are indexed without a
restore, which is what happens on most real repositories.
"""
import json
import os
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

import buildlog
import stages
import workarea
from adapters import OUTPUTS
from conftest import build_cs_repo
from test_cs_semgrep_slow import BLIND, IO

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")

NOT_TRUSTED = "The ref is not trusted, so scip-dotnet did not run. Use --allow-ref to run it."
# marker -> (kind, name) of the entry point that sits on or under it
ENTRIES = {"ep-program": ("program-main", "Shop.Api"), "ep-main": ("program-main", "Legacy"), "ep-apphost": ("program-main", "AppHost"), "ep-sample": ("program-main", "Sample"),
           "ep-target": ("build-target", "default"), "ep-cli": ("cli-command", "sync"), "ep-cron": ("scheduled-job", "nightly"),
           "ep-queue": ("queue-consumer", "MailConsumer"), "ep-ctl-list": ("http-route", "GET /api/Orders"),
           "ep-ctl-get": ("http-route", "GET /api/Orders/{id}"), "ep-ctl-abs": ("http-route", "POST /submit"), "ep-func": ("function", "Ping"),
           "ep-func-timer": ("scheduled-job", "Tick"), "ep-grpc": ("grpc-service", "Greeter"), "ep-hub": ("signalr-hub", "/chat"),
           "ep-hosted-add": ("hosted-service", "Cleanup"), "ep-hosted": ("hosted-service", "Cleanup"), "ep-min-get": ("http-route", "GET /health"),
           "ep-min-post": ("http-route", "POST /orders"), "ep-blazor": ("ui-route", "/counter"), "ep-razor": ("http-route", "GET /")}
# Real entry points the fixture has no marker for: the build project's own Main, and the second Bullseye target on the line below @ep-target.
UNMARKED = {("program-main", "build", "build/Program.cs"), ("build-target", "test", "build/Program.cs")}
# An Azure Functions entry sits on its [Function] attribute line; the marker is on the method line below it.
ATTRIBUTE_ABOVE = {"ep-func", "ep-func-timer"}
BLIND_ALL = {**BLIND, "bs-codegen": "codegen"}


class Extracted:
    def __init__(self, base, trusted=True):
        self.base = base
        self.repo = build_cs_repo(base)
        self.top, self.sha = self.repo.path, self.repo.sha
        self.out = base / "home" / "csrepo"
        self.area = workarea.area_for("csrepo", self.top, self.sha, base / "cache")
        self.tree = stages.tree_at(self.top, self.sha)
        self.trust = workarea.trusted(self.top, self.sha) if trusted else {"trusted": False, "why": "made for this test", "default_branch": None}
        self.build = buildlog.start(self.out, repo="csrepo", sha=self.sha, ref="main", version="test", options={})
        self.opts = stages.Options(restore="yes", allow_ref=False)
        copied = stages.stage_copy(self.build, self.top, self.sha, self.area, {}, self.opts, self.tree, self.trust)
        self.checkout, self.restore, self.restored = Path(copied["checkout"]["path"]), copied["restore"], copied["restored"]
        self.root = Path(self.top)

    def run(self):
        return stages.stage_extract(self.build, self.top, self.sha, self.area, self.out, ["C#"], self.trust, self.opts, self.restored, self.tree, self.checkout)

    def section(self, output, adapter="csharp"):
        return json.loads((self.out / "extract" / f"{output}.json").read_text())["adapters"][adapter]["items"]

    def markers(self):
        found: dict = {}
        for p in sorted(self.root.rglob("*")):
            if p.is_file() and ".git" not in p.parts and p.suffix in (".cs", ".razor", ".cshtml"):
                for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                    for m in re.findall(r"@([a-z0-9-]+)", line):
                        found.setdefault(m, []).append((str(p.relative_to(self.root)), n))
        return found

    def tools(self):
        cs = next(a for a in self.record["details"]["adapters"] if a["name"] == "csharp")
        return {t: s["status"] for t, s in cs["tools"].items()}, cs["tools"]


def _covers(rows, path, line):
    return [r for r in rows if r["path"] == path and r["line"] <= line <= (r.get("end_line") or r["line"])]


@pytest.fixture(scope="module")
def ex(tmp_path_factory):
    base = tmp_path_factory.mktemp("csadapter")
    patch = pytest.MonkeyPatch()
    patch.setenv("DOSSIER_HOME", str(base / "home"))
    patch.setenv("DOSSIER_CONFIG", str(base / "cfg.json"))
    patch.setenv("DOSSIER_CACHE", str(base / "cache"))
    try:
        e = Extracted(base)
        e.record = e.run()
        e.marks = e.markers()
        yield e
    finally:
        patch.undo()
        shutil.rmtree(base, ignore_errors=True)


class TestToolsAndOutputs:
    def test_every_output_has_a_csharp_section(self, ex):
        for name in OUTPUTS:
            assert "csharp" in json.loads((ex.out / "extract" / f"{name}.json").read_text())["adapters"]

    def test_only_shop_core_was_restored_and_it_worked(self, ex):
        assert [(r["ecosystem"], r["status"], r.get("dir")) for r in ex.restore] == [("nuget", "ok", "src/Shop.Core")]

    def test_every_tool_is_ok(self, ex):
        states, tools = ex.tools()

        assert states == {"scip-dotnet": "ok", "semgrep": "ok", "tree-sitter-language-pack": "ok"}, tools

    def test_every_candidate_has_an_id_and_a_group(self, ex):
        for output in ("entry_points", "io_candidates", "models", "dead", "blindspots"):
            assert all(i.get("id") and i.get("group") for i in ex.section(output)), output

    def test_second_run_is_reused(self, ex):
        assert ex.run()["status"] == "reused"

    def test_checkout_has_no_tracked_change_and_the_index_is_outside_it(self, ex):
        status = subprocess.run(["git", "-C", str(ex.checkout), "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True).stdout

        assert status == "" and not list(ex.checkout.rglob("*.scip"))


class TestEntryPoints:
    def test_rows_are_exactly_the_marked_ones_plus_the_two_unmarked_build_rows(self, ex):
        rows = ex.section("entry_points")

        assert len(rows) == len(ENTRIES) + len(UNMARKED)
        assert {(r["kind"], r["name"], r["path"]) for r in rows if r["path"].startswith("build/")} == UNMARKED | {("build-target", "default", "build/Program.cs")}

    @pytest.mark.parametrize("marker", sorted(ENTRIES))
    def test_each_marker_has_its_entry_point_on_its_line(self, ex, marker):
        assert ex.marks[marker], marker
        for path, line in ex.marks[marker]:
            at = line - 1 if marker in ATTRIBUTE_ABOVE else line
            assert ENTRIES[marker] in {(r["kind"], r["name"]) for r in _covers(ex.section("entry_points"), path, at)}, (marker, path, line)

    def test_near_miss_and_the_plain_controller_give_nothing(self, ex):
        rows = ex.section("entry_points")

        for path, line in ex.marks["not-route"]:
            assert not _covers(rows, path, line)
        assert not [r for r in rows if r["path"].endswith("HomeController.cs")]


class TestGraph:
    def test_one_project_item_for_each_project_and_the_references(self, ex):
        graph = ex.section("graph")

        names = {g["name"] for g in graph if g["kind"] == "cs-project"}
        refs = {(g["from"], g["to"]) for g in graph if g["kind"] == "project-reference"}
        assert names == {"AppHost", "build", "Legacy", "Sample", "Shop.Api", "Shop.Core", "Shop.Data", "Shop.NUnitTests", "Shop.Tests"}
        assert refs == {("Shop.Api", "Shop.Core"), ("Shop.Api", "Shop.Data"), ("Shop.Data", "Shop.Core"), ("Shop.Tests", "Shop.Api")}

    def test_source_roots_are_src_and_tests_and_none_is_the_build_folder(self, ex):
        roots = {g["path"]: g["root"] for g in ex.section("graph") if g["kind"] == "source-root"}

        assert {"src", "tests"} <= set(roots.values()) and "build/build.csproj" not in roots

    def test_the_designer_file_is_a_generated_module(self, ex):
        generated = [g["path"] for g in ex.section("graph") if g["kind"] == "module" and g.get("generated")]

        assert generated == ["src/Shop.Data/Migrations/20260101000000_Init.Designer.cs"]

    def test_type_use_edges_follow_the_using_directives(self, ex):
        edges = {(g["path"], g["paths"][0]) for g in ex.section("graph") if g["kind"] == "import"}

        assert {("src/Shop.Api/Services/OrderService.cs", "src/Shop.Core/Order.cs"), ("src/Shop.Data/ShopContext.cs", "src/Shop.Core/Customer.cs"),
                ("src/Shop.Core/Order.cs", "src/Shop.Core/Customer.cs")} <= edges

    def test_the_two_item_files_are_not_linked_and_the_name_is_noted(self, ex):
        graph = ex.section("graph")
        items = {"src/Shop.Core/Models/Item.cs", "src/Shop.Data/Models/Item.cs"}

        assert not [g for g in graph if g["kind"] == "import" and g["paths"][0] in items]
        assert [g["name"] for g in graph if g.get("note") == "ambiguous-name"] == ["1"]

    def test_notes_for_razor_frameworks_generators_and_missing_locks(self, ex):
        notes = [(g["note"], g["name"]) for g in ex.section("graph") if g["kind"] == "cs-note"]

        assert {("razor", "2"), ("framework", "FastEndpoints"), ("framework", "Aspire.Hosting.AppHost"), ("generator", "Riok.Mapperly|src/Shop.Api/Shop.Api.csproj"), ("dead", "1")} <= set(notes)
        assert sum(1 for n, _ in notes if n == "no-lock") == 8

    def test_shop_core_lists_its_friend(self, ex):
        core = next(g for g in ex.section("graph") if g["kind"] == "cs-project" and g["name"] == "Shop.Core")

        assert core["friends"] == ["Shop.Tests"]


class TestSymbols:
    def test_scip_defs_carry_the_public_flag(self, ex):
        flags = {s["name"]: s["public"] for s in ex.section("symbols") if s["kind"] == "def" and s["path"].startswith("src/Shop.Core/") and "via" not in s}

        assert flags["Order"] is True and flags["Secret"] is False

    def test_references_inside_the_restored_project_are_edges(self, ex):
        edges = {(s["path"], s["paths"][0]) for s in ex.section("symbols") if s["kind"] == "ref-edge"}

        assert ("src/Shop.Core/Order.cs", "src/Shop.Core/Customer.cs") in edges

    def test_a_cross_project_edge_from_the_api_to_core(self, ex):
        assert any(s["kind"] == "ref-edge" and s["path"].startswith("src/Shop.Api/") and s["paths"][0].startswith("src/Shop.Core/") for s in ex.section("symbols"))

    def test_no_edge_joins_the_program_classes_of_unrelated_projects(self, ex):
        programs = [s for s in ex.section("symbols") if s["kind"] == "ref-edge" and s["path"].endswith("/Program.cs") and s["paths"][0].endswith("/Program.cs")
                    and s["path"].split("/")[1] != s["paths"][0].split("/")[1]]
        cs = next(a for a in ex.record["details"]["adapters"] if a["name"] == "csharp")

        assert programs == []
        assert isinstance(cs["details"]["dropped_edges"], int)
        print("dropped_edges =", cs["details"]["dropped_edges"])

    def test_the_two_item_types_have_no_definition(self, ex):
        assert not [s for s in ex.section("symbols") if s["kind"] == "def" and s["name"] == "Item"]

    def test_public_api_of_shop_core(self, ex):
        rows = {s["name"]: s for s in ex.section("symbols") if s["kind"] == "public-api" and s["package"] == "Shop.Core"}

        assert {"Order", "IClock", "IClock.Now", "Money.Round", "Money.Shout", "Outer", "Outer.Inner", "Outer.P", "Hidden", "Totals", "Totals.Average"} <= set(rows)
        assert rows["Money.Round"]["symbol_kind"] == "method (2 overloads)" and rows["Money.Shout"]["symbol_kind"] == "extension method"
        assert rows["Hidden"]["audience"] == "packable, hidden from editors" and rows["Order"]["subpath"] == "Shop.Core"

    def test_public_api_leaves_out_internal_private_generated_and_application_names(self, ex):
        rows = [s for s in ex.section("symbols") if s["kind"] == "public-api"]

        assert not {"Secret", "Outer.Q", "CallerArgumentExpressionAttribute"} & {s["name"] for s in rows}
        assert not [s for s in rows if s["path"].endswith(".Designer.cs") or s["path"].startswith(("src/Shop.Api/", "tests/"))]
        assert {s["package"] for s in rows} == {"Shop.Core", "Shop.Data"}


class TestInputs:
    @pytest.mark.parametrize("marker,category", sorted(IO.items()))
    def test_each_io_marker_has_its_category(self, ex, marker, category):
        assert ex.marks[marker], marker
        for path, line in ex.marks[marker]:
            assert category in {r["category"] for r in _covers(ex.section("io_candidates"), path, line)}, (marker, path, line)

    def test_static_state_is_global_state(self, ex):
        for path, line in ex.marks["state-static"]:
            assert "global-state" in {r["category"] for r in _covers(ex.section("io_candidates"), path, line)}

    def test_appsettings_files_and_the_launch_profile_variable(self, ex):
        rows = ex.section("io_candidates")

        files = sorted(r["path"] for r in rows if r["rule"] == "cs.appsettings")
        launch = [(r["path"], r["line"], r["detail"]) for r in rows if r["rule"] == "cs.launch-env"]
        path = "src/Shop.Api/Properties/launchSettings.json"
        text = (ex.root / path).read_text().splitlines()
        assert files == ["src/Shop.Api/appsettings.Development.json", "src/Shop.Api/appsettings.json"]
        assert launch == [(path, next(n for n, t in enumerate(text, 1) if "ASPNETCORE_ENVIRONMENT" in t), "ASPNETCORE_ENVIRONMENT")]


class TestModelsTestsAndDead:
    def test_models_are_the_entities_the_enum_the_dapper_row_and_the_migrations(self, ex):
        got = {(m["kind"], m["name"]) for m in ex.section("models")}

        assert got == {("ef-entity", "Order"), ("ef-entity", "Customer"), ("cs-enum", "OrderStatus"), ("dapper-row", "Product"),
                       ("migration", "20260101000000_Init"), ("migration", "ShopContextModelSnapshot")}

    def test_test_files_and_their_counts(self, ex):
        files = {t["path"]: t for t in ex.section("tests") if t["kind"] == "test-file"}

        assert sorted(files) == ["tests/Shop.NUnitTests/MathTests.cs", "tests/Shop.Tests/OrdersTests.cs", "tests/Shop.Tests/TestHelpers.cs"]
        orders = files["tests/Shop.Tests/OrdersTests.cs"]
        assert (orders["framework"], orders["tests"], orders["skips"], orders["mocks"]) == ("xunit", 4, 1, 1)
        assert (files["tests/Shop.NUnitTests/MathTests.cs"]["tests"], files["tests/Shop.NUnitTests/MathTests.cs"]["skips"]) == (2, 1)

    def test_the_ci_file_gives_a_dotnet_test_command(self, ex):
        assert [t["command"] for t in ex.section("tests", "repo") if t["kind"] == "ci-command"] == ["dotnet test"]

    def test_the_only_dead_type_is_secret(self, ex):
        rows = ex.section("dead")

        assert [(r["name"], r["rule"], r["type"]) for r in rows] == [("Secret", "scip-dotnet.unused-type", "dead code without references")]

    def test_every_blind_spot_marker_has_its_pattern(self, ex):
        rows = ex.section("blindspots")

        for marker, pattern in BLIND_ALL.items():
            assert ex.marks[marker], marker
            for path, line in ex.marks[marker]:
                assert pattern in {r["pattern"] for r in _covers(rows, path, line)}, (marker, path, line)


class TestOtherRuns:
    def run(self, tmp_path_factory, monkeypatch, name, trusted=True, path=None):
        base = tmp_path_factory.mktemp(name)
        for key, value in (("DOSSIER_HOME", base / "home"), ("DOSSIER_CONFIG", base / "cfg.json"), ("DOSSIER_CACHE", base / "cache")):
            monkeypatch.setenv(key, str(value))
        if path:
            monkeypatch.setenv("PATH", path + os.pathsep + os.environ["PATH"])
        e = Extracted(base, trusted=trusted)
        e.record = e.run()
        return e

    def test_untrusted_ref_skips_scip_dotnet_and_changes_no_entry_point(self, ex, tmp_path_factory, monkeypatch):
        other = self.run(tmp_path_factory, monkeypatch, "csuntrusted", trusted=False)
        try:
            states, tools = other.tools()

            assert tools["scip-dotnet"] == {"status": "skipped", "reason": NOT_TRUSTED} and states["semgrep"] == states["tree-sitter-language-pack"] == "ok"
            assert other.section("entry_points") == ex.section("entry_points")
            assert any(s.get("via") == "tree-sitter" for s in other.section("symbols"))
            assert other.section("dead") == []
        finally:
            shutil.rmtree(other.base, ignore_errors=True)

    def test_without_an_sdk_scip_dotnet_and_the_restore_are_skipped_and_the_rest_is_kept(self, ex, tmp_path_factory, monkeypatch):
        fake = tmp_path_factory.mktemp("fakedotnet")
        (fake / "dotnet").write_text(textwrap.dedent("""\
            #!/bin/sh
            exit 0
            """))
        (fake / "dotnet").chmod(0o755)
        other = self.run(tmp_path_factory, monkeypatch, "csnosdk", path=str(fake))
        try:
            _, tools = other.tools()

            assert tools["scip-dotnet"]["status"] == "skipped" and "SDK" in tools["scip-dotnet"]["reason"]
            assert [r["status"] for r in other.restore] == ["skipped"] and "SDK" in other.restore[0]["reason"]
            assert tools["semgrep"]["status"] == tools["tree-sitter-language-pack"]["status"] == "ok"
            assert other.section("entry_points") == ex.section("entry_points")
            assert other.section("models") == ex.section("models")
        finally:
            shutil.rmtree(other.base, ignore_errors=True)
