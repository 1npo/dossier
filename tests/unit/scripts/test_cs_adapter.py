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
    def test_trusted_with_sdk_defers_every_tool_to_a_later_task(self, cs_repo, tmp_path, monkeypatch):
        _, ctx = extract(cs_repo, tmp_path, monkeypatch)

        assert {t: s["status"] for t, s in ctx.tool_status.items()} == {t: "skipped" for t in cs_adapter.CSharpAdapter.tools}
        assert all(s["reason"] == "Arrives in a later task." for s in ctx.tool_status.values())

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
