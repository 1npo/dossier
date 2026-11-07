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
    def query(self, language, paths, query):
        return []


class FakeSemgrep:
    def scan(self, config, paths=None, timeout=30):
        return []


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


@pytest.fixture(name="offline_tools")
def offline_tools_fixture(monkeypatch, tmp_path):
    """Stand in for the install and the two Node clients, so a unit test never starts Node."""
    monkeypatch.setattr(js_tools, "ensure_installed", lambda run, cache, timeout: Path("/nonexistent"))
    monkeypatch.setattr(js_tools.TsFacts, "facts", lambda self, d, files, entries=None: {"config": {"used": None}, "imports": [], "exports": [], "types": [],
                                                                             "components": [], "routes": [], "errors": []})
    monkeypatch.setattr(js_tools.DepCruiser, "cruise", lambda self, d, ts=None: {"modules": []})
    monkeypatch.setattr(js_tools.DepCruiser, "violations", lambda self, d, c: [])
    monkeypatch.setattr(js_tools.Knip, "run_knip", lambda self, d: {"issues": []})
    empty = tmp_path / "empty.scip"
    empty.write_bytes(b"")
    monkeypatch.setattr(js_tools.ScipTs, "index", lambda self, d, area, n, has_ts: empty)


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

    def test_semgrep_and_tree_sitter_run_without_node(self, js_repo, tmp_path):
        ctx = context(js_repo, tmp_path, run=node_run(code=127))

        js_adapter.JsAdapter().extract(ctx)

        assert ctx.tool_status["semgrep"] == {"status": "ok", "reason": None}
        assert ctx.tool_status["tree-sitter-language-pack"] == {"status": "ok", "reason": None}

    def test_every_tool_of_the_adapter_has_a_status(self, js_repo, tmp_path, offline_tools):
        ctx = context(js_repo, tmp_path)

        js_adapter.JsAdapter().extract(ctx)

        assert set(ctx.tool_status) == set(js_adapter.JsAdapter.tools)


class TestGraphStep:
    def test_modules_come_from_the_tracked_files_and_a_failing_tool_is_reported_by_project(self, js_repo, tmp_path, monkeypatch, offline_tools):
        def boom(self, d, ts=None):
            raise js_tools.ToolError("Building the import graph failed (exit 1):\nbad")
        monkeypatch.setattr(js_tools.DepCruiser, "cruise", boom)
        ctx = context(js_repo, tmp_path)

        out = js_adapter.JsAdapter().extract(ctx)

        assert ctx.tool_status["dependency-cruiser"]["status"] == "failed"
        assert ctx.tool_status["dependency-cruiser"]["reason"].startswith("the repository root: Building the import graph failed")
        assert ctx.tool_status["typescript"] == {"status": "ok", "reason": None}
        assert not [g for g in out["graph"] if g["kind"] == "module"]

    def test_install_failure_marks_the_four_node_tools_failed(self, js_repo, tmp_path, monkeypatch, offline_tools):
        def fail(run, cache, timeout):
            raise js_tools.ToolError("Installing the JavaScript tools failed (exit 1):\nno network")
        monkeypatch.setattr(js_tools, "ensure_installed", fail)
        ctx = context(js_repo, tmp_path)

        js_adapter.JsAdapter().extract(ctx)

        for tool in NODE_TOOLS:
            assert ctx.tool_status[tool]["status"] == "failed" and "Installing" in ctx.tool_status[tool]["reason"]


class TestDeadStep:
    def test_knip_findings_become_dead_items(self, js_repo, tmp_path, monkeypatch, offline_tools):
        issue = {"issues": [{"file": "src/unused.ts", "files": [{"name": "src/unused.ts"}], "dependencies": [], "devDependencies": [], "exports": [], "types": []}]}
        monkeypatch.setattr(js_tools.Knip, "run_knip", lambda self, d: issue)
        ctx = context(js_repo, tmp_path)

        out = js_adapter.JsAdapter().extract(ctx)

        assert [(d["type"], d["path"]) for d in out["dead"]] == [("unused file", "src/unused.ts")]
        assert ctx.tool_status["knip"] == {"status": "ok", "reason": None}

    def test_a_knip_crash_marks_only_knip_failed(self, js_repo, tmp_path, monkeypatch, offline_tools):
        def crash(self, d):
            raise js_tools.ToolError("knip failed (exit 2): Could not load config")
        monkeypatch.setattr(js_tools.Knip, "run_knip", crash)
        ctx = context(js_repo, tmp_path)

        out = js_adapter.JsAdapter().extract(ctx)

        assert ctx.tool_status["knip"]["status"] == "failed" and "Could not load config" in ctx.tool_status["knip"]["reason"]
        assert ctx.tool_status["typescript"]["status"] == "ok" and out["dead"] == []


class TestSymbolsStep:
    def test_a_scip_failure_marks_only_scip_failed(self, js_repo, tmp_path, monkeypatch, offline_tools):
        def crash(self, d, area, n, has_ts):
            raise js_tools.ToolError("scip-typescript failed (exit 1):\nno documents")
        monkeypatch.setattr(js_tools.ScipTs, "index", crash)
        ctx = context(js_repo, tmp_path)

        out = js_adapter.JsAdapter().extract(ctx)

        assert ctx.tool_status["scip-typescript"]["status"] == "failed" and out["symbols"] == []
        assert ctx.tool_status["knip"]["status"] == "ok"

    def test_the_project_without_a_tsconfig_is_indexed_with_an_inferred_one(self, js_repo, tmp_path, monkeypatch, offline_tools):
        seen = []
        empty = tmp_path / "empty.scip"
        monkeypatch.setattr(js_tools.ScipTs, "index", lambda self, d, area, n, has_ts: seen.append(has_ts) or empty)

        js_adapter.JsAdapter().extract(context(js_repo, tmp_path))

        assert seen == [True]


class TestModelsStep:
    def test_prisma_models_and_findings_come_even_without_node(self, js_repo, tmp_path):
        ctx = context(js_repo, tmp_path, trusted=False)

        out = js_adapter.JsAdapter().extract(ctx)

        assert {m["name"] for m in out["models"] if m["kind"].startswith("prisma")} == {"User", "Post", "Role"}
        assert [i["name"] for i in out["io_candidates"] if i["category"] == "env-var"] == ["DATABASE_URL"]

    def test_typescript_entities_come_from_the_script_output(self, js_repo, tmp_path, monkeypatch, offline_tools):
        types = [{"path": "src/types.ts", "name": "Order", "kind": "interface", "line": 8, "end_line": 12, "exported": True, "object": True,
                  "bases": [], "decorators": [], "fields": []}]
        monkeypatch.setattr(js_tools.TsFacts, "facts", lambda self, d, files, entries=None: {"config": {"used": None}, "imports": [], "exports": [], "types": types,
                                                                                 "components": [], "routes": [], "errors": []})

        out = js_adapter.JsAdapter().extract(context(js_repo, tmp_path))

        assert [(m["name"], m["kind"]) for m in out["models"] if not m["kind"].startswith("prisma")] == [("Order", "ts-interface")]


class TestReactStep:
    FACTS = {"config": {"used": None}, "imports": [], "exports": [], "types": [], "errors": [],
             "components": [{"path": "src/App.tsx", "name": "App", "line": 1, "end_line": 5, "exported": True, "hooks": [], "provides": [], "consumes": [],
                             "renders": [{"name": "Button", "path": "src/main.ts"}]}],
             "routes": [{"path": "src/router.tsx", "line": 2, "end_line": 2, "route": "/", "resolved": True, "file": None, "framework": "react-router"}]}

    def test_components_routes_and_fallback_edges_appear_when_scip_did_not_run(self, js_repo, tmp_path, monkeypatch, offline_tools):
        monkeypatch.setattr(js_tools.TsFacts, "facts", lambda self, d, files, entries=None: TestReactStep.FACTS)
        monkeypatch.setattr(js_tools.ScipTs, "index", lambda *a: (_ for _ in ()).throw(js_tools.ToolError("scip-typescript failed")))
        ctx = context(js_repo, tmp_path)

        out = js_adapter.JsAdapter().extract(ctx)

        assert {g["kind"] for g in out["graph"]} >= {"ui-component", "renders"}
        assert [e["name"] for e in out["entry_points"] if e["kind"] == "ui-route"] == ["/"]
        assert out["symbols"] == [{"kind": "ref-edge", "path": "src/App.tsx", "paths": ["src/main.ts"], "count": 1}]

    def test_no_fallback_edge_when_scip_succeeded(self, js_repo, tmp_path, monkeypatch, offline_tools):
        monkeypatch.setattr(js_tools.TsFacts, "facts", lambda self, d, files, entries=None: TestReactStep.FACTS)

        out = js_adapter.JsAdapter().extract(context(js_repo, tmp_path))

        assert out["symbols"] == []


class TestPublicApiStep:
    def test_entries_are_sent_to_the_script_and_its_names_become_public_api_symbols(self, js_repo, tmp_path, monkeypatch, offline_tools):
        sent = []

        def facts(self, d, files, entries=None):
            sent.extend(entries or [])
            api = [{"entry": "packages/lib/src/index.ts", "subpath": ".", "name": "sum", "kind": "function", "path": "packages/lib/src/math.ts", "line": 1}]
            return {"config": {"used": None}, "imports": [], "exports": [], "types": [], "components": [], "routes": [], "errors": [],
                    "api": api, "api_unresolved": []}
        monkeypatch.setattr(js_tools.TsFacts, "facts", facts)

        out = js_adapter.JsAdapter().extract(context(js_repo, tmp_path))

        assert {"entry": "packages/lib/src/index.ts", "subpath": "."} in sent
        sums = [s for s in out["symbols"] if s["kind"] == "public-api"]
        assert [(s["package"], s["subpath"], s["name"], s["audience"]) for s in sums] == [("@shopjs/lib", ".", "sum", "not marked private")]

    def test_a_package_without_api_fields_sends_no_entries(self, js_repo, tmp_path, monkeypatch, offline_tools):
        sent = []
        monkeypatch.setattr(js_tools.TsFacts, "facts", lambda self, d, files, entries=None: sent.extend(entries or []) or
                            {"config": {"used": None}, "imports": [], "exports": [], "types": [], "components": [], "routes": [], "errors": []})

        js_adapter.JsAdapter().extract(context(js_repo, tmp_path))

        assert not [e for e in sent if e["entry"].startswith("packages/web/")]


class TestSemgrepStep:
    def test_results_become_entries_findings_and_blind_spots(self, js_repo, tmp_path):
        seen = {}

        class Semgrep:
            def scan(self, config, paths=None, timeout=30):
                seen["rules"], seen["paths"] = config, paths
                return [{"rule": "dossier.js.entry.http-route", "path": "src/main.ts", "start_line": 2, "end_line": 2, "snippet": "app.get('/',", "detail": "get('/",
                         "metadata": {"category": "entry", "kind": "http-route"}},
                        {"rule": "dossier.js.blindspot.react-context", "path": "src/c.tsx", "start_line": 1, "end_line": 1, "snippet": "x", "detail": None,
                         "metadata": {"category": "blindspot", "pattern": "react-context"}}]
        ctx = context(js_repo, tmp_path)
        ctx.semgrep = Semgrep()

        out = js_adapter.JsAdapter().extract(ctx)

        assert seen["rules"].name == "js" and "src/main.ts" in seen["paths"] and not [p for p in seen["paths"] if p.endswith(".d.ts")]
        assert [(e["kind"], e["name"]) for e in out["entry_points"] if e["rule"].startswith("dossier.js")] == [("http-route", "GET /")]
        assert [b["pattern"] for b in out["blindspots"]] == ["react-context"]

    def test_a_semgrep_failure_marks_only_semgrep_failed(self, js_repo, tmp_path):
        class Semgrep:
            def scan(self, config, paths=None, timeout=30):
                raise RuntimeError("semgrep failed\nboom")
        ctx = context(js_repo, tmp_path)
        ctx.semgrep = Semgrep()

        js_adapter.JsAdapter().extract(ctx)

        assert ctx.tool_status["semgrep"] == {"status": "failed", "reason": "semgrep failed"}
        assert ctx.tool_status["tree-sitter-language-pack"]["status"] == "ok"


class TestNotesStep:
    def test_unsupported_framework_bun_project_and_unscanned_files_become_notes(self, tmp_path, offline_tools):
        files = {"package.json": '{"name": "a", "dependencies": {"koa": "1"}}', "bun.lockb": "", "a.js": "", "b.mts": ""}
        for name, text in files.items():
            (tmp_path / name).write_text(text)
        ctx = SimpleNamespace(checkout=tmp_path, tree=frozenset(files), files=["a.js", "b.mts"], area=tmp_path / "area", run=node_run(), trusted=True,
                              tool_status={}, tool_versions={}, treesitter=FakeTS(), semgrep=FakeSemgrep(), sha="a" * 40, repo_name="r", restored={})

        out = js_adapter.JsAdapter().extract(ctx)

        notes = {(g["note"], g["name"]) for g in out["graph"] if g["kind"] == "js-note"}
        assert notes == {("framework", "Koa"), ("bun", "."), ("unscanned", "1")}
