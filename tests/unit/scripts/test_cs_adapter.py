import subprocess
from types import SimpleNamespace

import adapters
import cs_adapter
import cs_sdk
from adapters import OUTPUTS


class FakeTS:
    def query(self, language, paths, query):
        return []


class FakeSemgrep:
    def scan(self, config, paths=None, timeout=30):
        return []


def context(cs_repo, tmp_path, trusted=True):
    root = cs_repo.path
    tree = frozenset(subprocess.run(["git", "-C", root, "ls-files"], capture_output=True, text=True).stdout.split())
    files = sorted(p for p in tree if p.endswith(".cs"))
    return SimpleNamespace(checkout=__import__("pathlib").Path(root), sha=cs_repo.sha, tree=tree, files=files, area=tmp_path / "area",
                           restored={}, run=None, treesitter=FakeTS(), semgrep=FakeSemgrep(), tool_versions={}, trusted=trusted,
                           repo_name="csrepo", tool_status={})


def extract(cs_repo, tmp_path, monkeypatch, trusted=True, sdks=("10.0.403",)):
    monkeypatch.setattr(cs_sdk, "list_sdks", lambda path=None: list(sdks))
    ctx = context(cs_repo, tmp_path, trusted)
    return cs_adapter.CSharpAdapter().extract(ctx), ctx


def notes(out, kind):
    return sorted((g["name"], g["path"]) for g in out["graph"] if g.get("kind") == "cs-note" and g["note"] == kind)


class TestDetect:
    def test_csharp_is_detected_for_csharp_only(self):
        assert [a.name for a in adapters.detect(["C#"])] == ["csharp", "repo"]
        assert "csharp" not in [a.name for a in adapters.detect(["Python"])]
        assert "csharp" not in [a.name for a in adapters.detect(["JavaScript", "TypeScript"])]

    def test_registered_order_puts_csharp_first(self):
        assert [a.name for a in adapters._registered()] == ["csharp", "js", "python", "repo"]

    def test_declared_properties(self):
        ad = cs_adapter.CSharpAdapter

        assert (ad.languages, ad.expected_untracked, ad.loads_repo_code) == (("C#",), ("**/bin/**", "**/obj/**", "artifacts/**"), False)
        assert ad.tools == ("scip-dotnet", "semgrep", "tree-sitter-language-pack")


class TestProjectItems:
    def test_every_output_is_present(self, cs_repo, tmp_path, monkeypatch):
        out, _ = extract(cs_repo, tmp_path, monkeypatch)

        assert set(out) == set(OUTPUTS)

    def test_one_cs_project_item_per_csharp_project(self, cs_repo, tmp_path, monkeypatch):
        out, _ = extract(cs_repo, tmp_path, monkeypatch)

        got = {g["name"]: g for g in out["graph"] if g["kind"] == "cs-project"}

        assert sorted(got) == ["Legacy", "Sample", "Shop.Api", "Shop.Core", "Shop.Data", "Shop.NUnitTests", "Shop.Tests", "build"]
        assert got["Shop.Api"]["sdk"] == "Microsoft.NET.Sdk.Web" and got["Shop.Tests"]["test"] is True
        assert got["Shop.Core"]["packable"] is True and got["Shop.Core"]["frameworks"] == ["net10.0"]

    def test_project_references_name_both_ends(self, cs_repo, tmp_path, monkeypatch):
        out, _ = extract(cs_repo, tmp_path, monkeypatch)

        refs = {(g["from"], g["to"]) for g in out["graph"] if g["kind"] == "project-reference"}

        assert refs == {("Shop.Api", "Shop.Core"), ("Shop.Api", "Shop.Data"), ("Shop.Data", "Shop.Core"), ("Shop.Tests", "Shop.Api")}

    def test_source_roots_are_the_parent_folders_of_the_projects(self, cs_repo, tmp_path, monkeypatch):
        out, _ = extract(cs_repo, tmp_path, monkeypatch)

        roots = sorted({g["root"] for g in out["graph"] if g["kind"] == "source-root"})

        assert roots == ["samples", "src", "tests", "tools"]


class TestNotes:
    def test_framework_note_for_fast_endpoints(self, cs_repo, tmp_path, monkeypatch):
        out, _ = extract(cs_repo, tmp_path, monkeypatch)

        assert notes(out, "framework") == [("FastEndpoints", "src/Shop.Api/Shop.Api.csproj")]

    def test_no_lock_note_for_every_project_except_core(self, cs_repo, tmp_path, monkeypatch):
        out, _ = extract(cs_repo, tmp_path, monkeypatch)

        assert [n for n, _ in notes(out, "no-lock")] == ["Legacy", "Sample", "Shop.Api", "Shop.Data", "Shop.NUnitTests", "Shop.Tests", "build"]

    def test_one_razor_note_counts_two_files(self, cs_repo, tmp_path, monkeypatch):
        out, _ = extract(cs_repo, tmp_path, monkeypatch)

        assert notes(out, "razor") == [("2", "src/Shop.Api/Components/Pages/Counter.razor")]


class TestToolStatus:
    def test_trusted_with_sdk_defers_the_tools_not_built_yet_to_a_later_task(self, cs_repo, tmp_path, monkeypatch):
        _, ctx = extract(cs_repo, tmp_path, monkeypatch)

        assert {t: s["status"] for t, s in ctx.tool_status.items()} == {"scip-dotnet": "skipped", "semgrep": "skipped", "tree-sitter-language-pack": "ok"}
        assert all(s["reason"] == "Arrives in a later task." for t, s in ctx.tool_status.items() if t != "tree-sitter-language-pack")

    def test_untrusted_ref_gives_the_trust_reason_for_scip_dotnet(self, cs_repo, tmp_path, monkeypatch):
        _, ctx = extract(cs_repo, tmp_path, monkeypatch, trusted=False)

        assert ctx.tool_status["scip-dotnet"] == {
            "status": "skipped", "reason": "The ref is not trusted, so scip-dotnet did not run. Use --allow-ref to run it."}

    def test_missing_sdk_gives_the_sdk_reason_for_scip_dotnet(self, cs_repo, tmp_path, monkeypatch):
        _, ctx = extract(cs_repo, tmp_path, monkeypatch, sdks=())

        assert ctx.tool_status["scip-dotnet"] == {"status": "skipped", "reason": "The .NET SDK is not installed."}

    def test_sdk_that_does_not_satisfy_global_json_gives_that_reason(self, cs_repo, tmp_path, monkeypatch):
        _, ctx = extract(cs_repo, tmp_path, monkeypatch, sdks=("10.0.114",))

        assert ctx.tool_status["scip-dotnet"]["reason"].startswith("The repository asks for .NET SDK 10.0.403 (latestFeature) in global.json")

    def test_semgrep_and_tree_sitter_do_not_depend_on_trust_or_sdk(self, cs_repo, tmp_path, monkeypatch):
        _, ctx = extract(cs_repo, tmp_path, monkeypatch, trusted=False, sdks=())

        assert ctx.tool_status["semgrep"]["reason"] == "Arrives in a later task."


def _d(namespaces, types, usings=(), idents=()):
    return {"namespaces": [{"name": n} for n in namespaces], "types": types, "qualified": [], "idents": {i: [5] for i in idents},
            "usings": [{"name": u, "global": False, "static": False, "alias": None} for u in usings], "top_level": False,
            "assembly_attributes": []}


def _ty(name, ns):
    return {"name": name, "namespace": ns, "partial": False, "kind": "class", "modifiers": ["public"], "line": 1, "end_line": 9, "bases": [],
            "attributes": [], "members": [], "params": [], "outer": None}


def with_decls(monkeypatch, table):
    import cs_queries
    monkeypatch.setattr(cs_queries, "declarations", lambda ts, files: {f: table.get(f, _d([], [])) for f in files})
    monkeypatch.setattr(cs_queries, "complexity", lambda ts, files: {f: 3 for f in files})


ORDER, SERVICE = "src/Shop.Core/Order.cs", "src/Shop.Api/Services/OrderService.cs"
TESTS = "tests/Shop.Tests/OrdersTests.cs"


class TestGraph:
    def _run(self, cs_repo, tmp_path, monkeypatch):
        with_decls(monkeypatch, {ORDER: _d(["Shop.Core"], [_ty("Order", "Shop.Core")]),
                                 SERVICE: _d(["Shop.Api.Services"], [_ty("OrderService", "Shop.Api.Services")], ["Shop.Core"], ["Order"]),
                                 TESTS: _d(["Shop.Tests"], [_ty("OrdersTests", "Shop.Tests")], ["Shop.Core"], ["Order"])})
        return extract(cs_repo, tmp_path, monkeypatch)

    def test_module_items_exist_for_source_files_and_not_for_test_files(self, cs_repo, tmp_path, monkeypatch):
        out, _ = self._run(cs_repo, tmp_path, monkeypatch)
        modules = {g["path"]: g for g in out["graph"] if g["kind"] == "module"}

        assert ORDER in modules and TESTS not in modules
        assert modules[ORDER]["project"] == "src/Shop.Core/Shop.Core.csproj" and modules[ORDER]["complexity"] == 3
        assert modules["src/Shop.Data/Migrations/20260101000000_Init.Designer.cs"]["generated"] is True
        assert modules[ORDER]["generated"] is False

    def test_a_type_use_makes_an_import_item(self, cs_repo, tmp_path, monkeypatch):
        out, _ = self._run(cs_repo, tmp_path, monkeypatch)

        imports = [g for g in out["graph"] if g["kind"] == "import"]

        assert [(i["path"], i["paths"], i["via"]) for i in imports] == [(SERVICE, [ORDER], "type-use")]

    def test_a_tree_sitter_failure_marks_the_tool_failed_and_still_gives_projects(self, cs_repo, tmp_path, monkeypatch):
        import cs_queries

        def boom(ts, files):
            raise RuntimeError("grammar missing\nmore")
        monkeypatch.setattr(cs_queries, "declarations", boom)

        out, ctx = extract(cs_repo, tmp_path, monkeypatch)

        assert ctx.tool_status["tree-sitter-language-pack"] == {"status": "failed", "reason": "grammar missing"}
        assert any(g["kind"] == "cs-project" for g in out["graph"]) and not any(g["kind"] == "module" for g in out["graph"])

    def test_ambiguous_names_make_a_note(self, cs_repo, tmp_path, monkeypatch):
        with_decls(monkeypatch, {"src/Shop.Core/Order.cs": _d(["Shop.Core"], [_ty("Item", "Shop.Core")]),
                                 "src/Shop.Core/Customer.cs": _d(["Shop.Core.Other"], [_ty("Item", "Shop.Core.Other")]),
                                 SERVICE: _d(["Shop.Api"], [], ["Shop.Core", "Shop.Core.Other"], ["Item"])})

        out, _ = extract(cs_repo, tmp_path, monkeypatch)

        assert notes(out, "ambiguous-name")[0][0] == "1"


class TestEntryPoints:
    def test_razor_pages_are_found_without_tree_sitter(self, cs_repo, tmp_path, monkeypatch):
        out, _ = extract(cs_repo, tmp_path, monkeypatch)

        got = {(e["kind"], e["name"], e["path"]) for e in out["entry_points"]}

        assert ("ui-route", "/counter", "src/Shop.Api/Components/Pages/Counter.razor") in got
        assert ("http-route", "GET /", "src/Shop.Api/Pages/Index.cshtml") in got

    def test_declaration_entries_are_added_when_tree_sitter_ran(self, cs_repo, tmp_path, monkeypatch):
        controller = {"name": "OrdersController", "kind": "class", "modifiers": ["public"], "line": 3, "end_line": 9, "bases": ["ControllerBase"], "partial": False,
                      "outer": None, "namespace": "N", "params": [], "attributes": [{"name": "Route", "args": '"api/o"', "line": 2}],
                      "members": [{"name": "List", "kind": "method", "modifiers": ["public"], "line": 5, "end_line": 5, "static": False, "params": [], "type": "X",
                                   "attributes": [{"name": "HttpGet", "args": "", "line": 4}]}]}
        with_decls(monkeypatch, {"src/Shop.Api/Controllers/OrdersController.cs": _d(["N"], [controller])})

        out, _ = extract(cs_repo, tmp_path, monkeypatch)

        assert ("GET /api/o", 5) in [(e["name"], e["line"]) for e in out["entry_points"] if e["path"].endswith("OrdersController.cs")]


class TestModels:
    def test_models_come_from_the_declarations_and_migrations_are_read_in_generated_files(self, cs_repo, tmp_path, monkeypatch):
        order = {**_ty("Order", "Shop.Core"), "members": [{"name": "Id", "kind": "property", "modifiers": ["public"], "line": 5, "end_line": 5, "attributes": [],
                                                              "type": "int", "static": False, "params": [], "get": True}]}
        ctx_type = {**_ty("ShopContext", "Shop.Data"), "bases": ["DbContext"],
                    "members": [{"name": "Orders", "kind": "property", "modifiers": ["public"], "line": 5, "end_line": 5, "attributes": [], "type": "DbSet<Order>",
                                 "static": False, "params": [], "get": True}]}
        designer = "src/Shop.Data/Migrations/20260101000000_Init.Designer.cs"
        mig = {**_ty("Init", "Shop.Data.Migrations"), "bases": ["Migration"], "attributes": [{"name": "Migration", "args": '"2026_Init"', "line": 1}]}
        with_decls(monkeypatch, {"src/Shop.Core/Order.cs": _d(["Shop.Core"], [order]), "src/Shop.Data/ShopContext.cs": _d(["Shop.Data"], [ctx_type], ["Shop.Core"]),
                                 designer: _d(["Shop.Data.Migrations"], [mig])})

        out, _ = extract(cs_repo, tmp_path, monkeypatch)

        assert sorted((m["kind"], m["name"]) for m in out["models"]) == [("ef-entity", "Order"), ("migration", "2026_Init")]


class TestTests:
    def test_test_files_come_from_test_projects_with_edges_to_the_code_they_use(self, cs_repo, tmp_path, monkeypatch):
        fact = {"name": "Adds", "kind": "method", "modifiers": ["public"], "line": 5, "end_line": 5, "attributes": [{"name": "Fact", "args": "", "line": 4}],
                "type": "void", "static": False, "params": []}
        tests_type = {**_ty("OrdersTests", "Shop.Tests"), "members": [fact]}
        state = {"name": "_count", "kind": "field", "modifiers": ["static"], "line": 5, "end_line": 5, "attributes": [], "type": "int", "static": True, "params": [], "init": ""}
        service = {**_ty("OrderService", "Shop.Api.Services"), "members": [state]}
        with_decls(monkeypatch, {ORDER: _d(["Shop.Core"], [_ty("Order", "Shop.Core")]), TESTS: _d(["Shop.Tests"], [tests_type], ["Shop.Core"], ["Order"]),
                                 SERVICE: _d(["Shop.Api.Services"], [service])})

        out, _ = extract(cs_repo, tmp_path, monkeypatch)
        item = {t["path"]: t for t in out["tests"] if t["kind"] == "test-file"}[TESTS]

        assert (item["framework"], item["tests"], item["test_kind"], item["paths"], item["imports"]) == ("xunit", 1, "integration", [ORDER], ["src/Shop.Core/Order"])
        assert [(s["path"], s["name"]) for s in out["io_candidates"] if s["category"] == "global-state"] == [(SERVICE, "_count")]

    def test_config_items_are_listed(self, cs_repo, tmp_path, monkeypatch):
        out, _ = extract(cs_repo, tmp_path, monkeypatch)

        assert all(c["kind"] in ("config", "test-file") for c in out["tests"])
