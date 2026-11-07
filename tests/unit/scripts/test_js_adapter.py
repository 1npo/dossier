import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import adapters
import js_adapter
import js_tools
from adapters import OUTPUTS

NODE_TOOLS = ("dependency-cruiser", "knip", "scip-typescript", "typescript")


class FakeTS:
    pass


class FakeSemgrep:
    pass


def node_run(version="v26.13.0", code=0):
    def run(cmd, *, stage, profile, timeout, cwd=None):
        assert cmd == ["node", "--version"]
        return SimpleNamespace(returncode=code, timed_out=False, stdout=_file(version), stderr=_file(""))
    return run


_n = [0]


def _file(text, root=[None]):
    import tempfile
    _n[0] += 1
    p = Path(tempfile.mkdtemp()) / f"o{_n[0]}"
    p.write_text(text)
    return p


def context(js_repo, tmp_path, trusted=True, run=None):
    root = Path(js_repo.path)
    tree = frozenset(subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True).stdout.split())
    files = sorted(p for p in tree if p.endswith((".ts", ".tsx", ".js", ".jsx")))
    return SimpleNamespace(checkout=root, sha=js_repo.sha, tree=tree, files=files, area=tmp_path / "area", restored={}, run=run or node_run(),
                           treesitter=FakeTS(), semgrep=FakeSemgrep(), tool_versions={}, trusted=trusted, repo_name="jsrepo", tool_status={})


class TestDetect:
    def test_typescript_and_javascript_include_js(self):
        assert "js" in [a.name for a in adapters.detect(["TypeScript"])]
        assert "js" in [a.name for a in adapters.detect(["JavaScript"])]

    def test_python_alone_does_not(self):
        assert "js" not in [a.name for a in adapters.detect(["Python"])]

    def test_js_comes_first_in_the_registered_order(self):
        assert [a.name for a in adapters.detect(["Python", "TypeScript"])] == ["js", "python", "repo"]


class TestAdapterShape:
    def test_description(self):
        a = js_adapter.JsAdapter()

        assert (a.name, a.version, a.languages, a.loads_repo_code, a.expected_untracked) == (
            "js", "1", ("JavaScript", "TypeScript"), False, ("**/node_modules/**",))
        assert a.tools == ("dependency-cruiser", "knip", "scip-typescript", "typescript", "semgrep", "tree-sitter-language-pack")


class TestEntryPoints:
    def test_package_nx_and_next_entries_come_from_project_files(self, js_repo, tmp_path):
        ctx = context(js_repo, tmp_path)

        out = js_adapter.JsAdapter().extract(ctx)

        assert set(out) == set(OUTPUTS)
        names = {(e["kind"], e["name"]) for e in out["entry_points"]}
        assert {("package-bin", "shopjs"), ("package-script", "shopjs start"), ("package-script", "prisma seed"),
                ("package-main", "dist/main.js"), ("nx-target", "shopjs:serve"), ("nx-target", "shopjs:build"),
                ("http-route", "/"), ("http-route", "/items/[id]"), ("http-route", "API /api/ping"), ("http-route", "/about")} <= names

    def test_next_routes_are_found_only_in_packages_that_depend_on_next(self, js_repo, tmp_path):
        out = js_adapter.JsAdapter().extract(context(js_repo, tmp_path))

        assert not [e for e in out["entry_points"] if e["kind"] == "http-route" and e["path"].startswith("packages/web/")]

    def test_workspace_member_manifests_are_read(self, js_repo, tmp_path):
        out = js_adapter.JsAdapter().extract(context(js_repo, tmp_path))

        assert any(e["kind"] == "package-main" and e["path"] == "packages/lib/package.json" for e in out["entry_points"])

    def test_items_have_the_fields_every_entry_point_has(self, js_repo, tmp_path):
        out = js_adapter.JsAdapter().extract(context(js_repo, tmp_path))

        for e in out["entry_points"]:
            assert {"path", "line", "end_line", "kind", "name", "trigger", "rule", "snippet"} <= set(e)

    def test_a_repository_without_package_files_gives_no_entries(self, tmp_path):
        repo = SimpleNamespace(path=str(tmp_path / "r"), sha="a" * 40)
        (tmp_path / "r").mkdir()
        (tmp_path / "r/a.js").write_text("")
        ctx = SimpleNamespace(checkout=tmp_path / "r", tree=frozenset({"a.js"}), files=["a.js"], area=tmp_path, run=node_run(), trusted=True,
                              tool_status={}, tool_versions={}, treesitter=None, semgrep=None, sha=repo.sha, repo_name="r", restored={})

        assert js_adapter.JsAdapter().extract(ctx)["entry_points"] == []


class TestGates:
    def test_untrusted_ref_skips_the_four_node_tools_with_the_fixed_reason(self, js_repo, tmp_path):
        ctx = context(js_repo, tmp_path, trusted=False)

        out = js_adapter.JsAdapter().extract(ctx)

        for tool in NODE_TOOLS:
            assert ctx.tool_status[tool] == {"status": "skipped", "reason": js_tools.NOT_TRUSTED}
        assert out["entry_points"]

    def test_old_node_skips_with_its_reason(self, js_repo, tmp_path):
        ctx = context(js_repo, tmp_path, run=node_run("v20.19.2"))

        js_adapter.JsAdapter().extract(ctx)

        for tool in NODE_TOOLS:
            assert ctx.tool_status[tool] == {"status": "skipped", "reason": "Node 20.19.2 is too old; these tools need 22.13.0 or later."}

    def test_missing_node_skips_with_its_reason(self, js_repo, tmp_path):
        ctx = context(js_repo, tmp_path, run=node_run(code=127))

        js_adapter.JsAdapter().extract(ctx)

        assert ctx.tool_status["knip"] == {"status": "skipped", "reason": "Node is not installed."}

    def test_not_yet_built_steps_say_so(self, js_repo, tmp_path):
        ctx = context(js_repo, tmp_path)

        js_adapter.JsAdapter().extract(ctx)

        for tool in ("semgrep", "tree-sitter-language-pack", *NODE_TOOLS):
            assert ctx.tool_status[tool] == {"status": "skipped", "reason": "Arrives in a later task."}

    def test_every_tool_of_the_adapter_has_a_status(self, js_repo, tmp_path):
        ctx = context(js_repo, tmp_path)

        js_adapter.JsAdapter().extract(ctx)

        assert set(ctx.tool_status) == set(js_adapter.JsAdapter.tools)
