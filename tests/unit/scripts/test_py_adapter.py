import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import adapters
import py_adapter
import scip_read
import scip_tool
from shared_tools import ToolError


class FakeTS:
    def query(self, language, paths, query):
        return []


class FakeSemgrep:
    def __init__(self, results=None, error=None):
        self.results, self.error, self.paths = results or [], error, None

    def scan(self, config, paths=None, timeout=30):
        self.paths = paths
        if self.error:
            raise self.error
        return self.results


class FakeGrimp:
    response = {"modules": [], "imports": [], "contracts": [], "errors": []}
    all = []
    error = None

    def __init__(self, run, timeout):
        self.calls = []

    def graph(self, roots, packages, contracts):
        FakeGrimp.args = (roots, packages, contracts)
        FakeGrimp.all.append(FakeGrimp.args)
        if FakeGrimp.error:
            raise FakeGrimp.error
        return FakeGrimp.response


class FakeVulture:
    items = []
    error = None
    calls = []

    def __init__(self, run, timeout):
        pass

    def dead(self, paths, config):
        FakeVulture.calls.append(paths)
        if FakeVulture.error:
            raise FakeVulture.error
        return FakeVulture.items


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    FakeGrimp.response = {"modules": [], "imports": [], "contracts": [], "errors": []}
    FakeVulture.items, FakeVulture.error = [], None
    FakeVulture.calls, FakeGrimp.all, FakeGrimp.error = [], [], None
    monkeypatch.setattr(py_adapter, "Grimp", FakeGrimp)
    monkeypatch.setattr(py_adapter, "Vulture", FakeVulture)
    monkeypatch.setattr(py_adapter.config, "timeouts", lambda: {"tool": 5})


def context(py_repo, tmp_path, semgrep=None, trusted=True):
    root = Path(py_repo.path)
    tree = frozenset(subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True).stdout.split())
    files = sorted(p for p in tree if p.endswith(".py"))
    return SimpleNamespace(checkout=root, sha=py_repo.sha, tree=tree, files=files, area=tmp_path / "area", restored={}, run=None,
                           treesitter=FakeTS(), semgrep=semgrep or FakeSemgrep(), tool_versions={"scip-python": "0.6.6"},
                           trusted=trusted, repo_name="pyrepo", tool_status={})


def graph_response(root):
    src = str(Path(root) / "src" / "shopcart")
    return {"modules": [{"module": "shopcart.a", "path": src + "/a.py", "is_package": False},
                        {"module": "shopcart.b", "path": src + "/b.py", "is_package": False},
                        {"module": "shopcart.core", "path": src + "/core.py", "is_package": False},
                        {"module": "shopcart.cli", "path": src + "/cli.py", "is_package": False}],
            "imports": [{"from": "shopcart.a", "to": "shopcart.b", "lines": [1]}, {"from": "shopcart.b", "to": "shopcart.a", "lines": [1]},
                        {"from": "shopcart.core", "to": "shopcart.cli", "lines": [7]}],
            "contracts": [{"name": "cli above core", "type": "layers", "status": "broken", "reason": None,
                           "violations": [{"from": "shopcart.core", "to": "shopcart.cli", "line": 7}]},
                          {"name": "apps apart", "type": "independence", "status": "not-checked", "reason": "no", "violations": []}],
            "errors": []}


class TestGraph:
    def test_modules_imports_cycles_and_contracts_become_graph_items(self, py_repo, tmp_path):
        FakeGrimp.response = graph_response(py_repo.path)

        out = py_adapter.PythonAdapter().extract(context(py_repo, tmp_path))

        by_kind = {}
        for item in out["graph"]:
            by_kind.setdefault(item["kind"], []).append(item)
        assert [m["module"] for m in by_kind["module"] if m["package"]] == ["shopcart.a", "shopcart.b", "shopcart.cli", "shopcart.core"]
        assert {(i["from"], i["to"], i["via"]) for i in by_kind["import"]} == {("shopcart.a", "shopcart.b", "grimp"),
                                                                                ("shopcart.b", "shopcart.a", "grimp"),
                                                                                ("shopcart.core", "shopcart.cli", "grimp")}
        assert by_kind["cycle"] == [{"kind": "cycle", "path": "src/shopcart/a.py", "paths": ["src/shopcart/a.py", "src/shopcart/b.py"],
                                     "modules": ["shopcart.a", "shopcart.b"]}]
        broken = next(c for c in by_kind["contract"] if c["contract"] == "cli above core")
        assert (broken["status"], broken["path"]) == ("broken", "pyproject.toml")
        assert broken["violations"] == [{"from": "shopcart.core", "to": "shopcart.cli", "path": "src/shopcart/core.py", "line": 7}]

    def test_grimp_gets_the_absolute_source_root_and_the_package(self, py_repo, tmp_path):
        py_adapter.PythonAdapter().extract(context(py_repo, tmp_path))

        roots, packages, contracts = FakeGrimp.args
        assert roots == [str(Path(py_repo.path) / "src")] and packages == ["shopcart"] and len(contracts) == 2

    def test_no_package_skips_grimp_with_the_fixed_reason(self, tmp_path):
        repo = tmp_path / "loose"
        repo.mkdir()
        (repo / "tool.py").write_text("print('x')\n")
        subprocess.run(["git", "-C", str(repo), "init", "-q", "-b", "main"], check=True)
        ctx = SimpleNamespace(checkout=repo, sha="a" * 40, tree=frozenset({"tool.py"}), files=["tool.py"], area=tmp_path / "area", restored={},
                              run=None, treesitter=FakeTS(), semgrep=FakeSemgrep(), tool_versions={}, trusted=False, repo_name="loose",
                              tool_status={})

        out = py_adapter.PythonAdapter().extract(ctx)

        assert ctx.tool_status["grimp"] == {"status": "skipped", "reason": py_adapter.NO_PACKAGE}
        assert [(g["module"], g["package"]) for g in out["graph"]] == [("tool", None)]


class TestToolIsolation:
    def test_a_failing_tool_leaves_the_other_outputs_and_is_marked_failed(self, py_repo, tmp_path):
        FakeGrimp.response = graph_response(py_repo.path)
        FakeVulture.error = ToolError("vulture failed (exit 1):\nboom")
        ctx = context(py_repo, tmp_path)

        out = py_adapter.PythonAdapter().extract(ctx)

        assert ctx.tool_status["vulture"] == {"status": "failed", "reason": "vulture failed (exit 1):"}
        assert ctx.tool_status["grimp"]["status"] == "ok" and out["graph"] and out["dead"] == []

    def test_semgrep_failure_is_recorded_and_the_rest_continues(self, py_repo, tmp_path):
        ctx = context(py_repo, tmp_path, semgrep=FakeSemgrep(error=RuntimeError("no rules")))

        out = py_adapter.PythonAdapter().extract(ctx)

        assert ctx.tool_status["semgrep"] == {"status": "failed", "reason": "no rules"} and out["entry_points"]

    def test_every_output_key_is_present(self, py_repo, tmp_path):
        out = py_adapter.PythonAdapter().extract(context(py_repo, tmp_path))

        assert set(out) == set(adapters.OUTPUTS)


class TestScip:
    def test_untrusted_ref_skips_scip_python_with_the_fixed_reason(self, py_repo, tmp_path):
        ctx = context(py_repo, tmp_path, trusted=False)

        py_adapter.PythonAdapter().extract(ctx)

        assert ctx.tool_status["scip-python"] == {"status": "skipped", "reason": py_adapter.NOT_TRUSTED}

    def test_missing_node_skips_scip_python(self, py_repo, tmp_path, monkeypatch):
        monkeypatch.setattr(py_adapter.shutil, "which", lambda *a, **k: None)
        ctx = context(py_repo, tmp_path)

        py_adapter.PythonAdapter().extract(ctx)

        assert ctx.tool_status["scip-python"] == {"status": "skipped", "reason": py_adapter.NO_NODE}

    def test_symbols_come_from_the_decoded_index(self, py_repo, tmp_path, monkeypatch):
        index = tmp_path / "index.scip"
        index.write_bytes(b"")
        monkeypatch.setattr(py_adapter.shutil, "which", lambda *a, **k: "/usr/bin/node")
        monkeypatch.setattr(scip_tool, "ensure_installed", lambda *a, **k: "/tool/index.js")
        monkeypatch.setattr(scip_tool, "run_index", lambda *a, **k: index)
        monkeypatch.setattr(scip_read, "reduce", lambda decoded: [{"kind": "def", "path": "src/shopcart/core.py", "line": 1, "name": "total"}])
        ctx = context(py_repo, tmp_path)

        out = py_adapter.PythonAdapter().extract(ctx)

        assert ctx.tool_status["scip-python"]["status"] == "ok" and out["symbols"][0]["name"] == "total"


class TestSemgrepPaths:
    def test_semgrep_is_given_the_tracked_python_files_including_tests(self, py_repo, tmp_path):
        semgrep = FakeSemgrep()

        py_adapter.PythonAdapter().extract(context(py_repo, tmp_path, semgrep=semgrep))

        assert "tests/test_core.py" in semgrep.paths and "src/shopcart/core.py" in semgrep.paths


class TestSemgrepRouting:
    def result(self, rule, path, line, **extra):
        return {"rule": rule, "path": path, "start_line": line, "end_line": line, "snippet": "x", "detail": None, "metadata": {}, **extra}

    def test_entry_rule_becomes_an_entry_point_with_its_function(self, py_repo, tmp_path):
        line = py_repo.line_of("src/shopcart/api.py", "ep-route")
        semgrep = FakeSemgrep([self.result("dossier.python.entry.http-route", "src/shopcart/api.py", line, detail="/cart",
                                           metadata={"category": "entry", "kind": "http-route"}, snippet='@app.route("/cart")')])
        FakeGrimp.response = graph_response(py_repo.path) | {"modules": [{"module": "shopcart.api", "path": str(Path(py_repo.path) / "src/shopcart/api.py"),
                                                                           "is_package": False}], "imports": [], "contracts": []}

        out = py_adapter.PythonAdapter().extract(context(py_repo, tmp_path, semgrep=semgrep))

        route = next(e for e in out["entry_points"] if e["kind"] == "http-route")
        assert (route["name"], route["target"], route["line"]) == ("/cart", "shopcart.api:cart", line)
        assert route["trigger"] == "a web request to `/cart`"

    def test_io_rule_becomes_an_io_candidate_with_its_category(self, py_repo, tmp_path):
        semgrep = FakeSemgrep([self.result("dossier.python.input.env-var", "src/shopcart/store.py", 4, detail="SHOP_DB",
                                           metadata={"category": "env-var"})])

        out = py_adapter.PythonAdapter().extract(context(py_repo, tmp_path, semgrep=semgrep))

        assert [(c["category"], c["detail"], c["rule"]) for c in out["io_candidates"]] == [("env-var", "SHOP_DB", "dossier.python.input.env-var")]

    def test_blindspot_rule_becomes_a_blindspot_with_its_pattern(self, py_repo, tmp_path):
        semgrep = FakeSemgrep([self.result("dossier.python.blindspot.dynamic-import", "src/shopcart/plugins.py", 5,
                                           metadata={"category": "blindspot", "pattern": "dynamic-import"})])

        out = py_adapter.PythonAdapter().extract(context(py_repo, tmp_path, semgrep=semgrep))

        assert [b["pattern"] for b in out["blindspots"]] == ["dynamic-import"]


class TestEntries:
    def test_console_script_and_main_module_come_from_project_files(self, py_repo, tmp_path):
        out = py_adapter.PythonAdapter().extract(context(py_repo, tmp_path))

        got = {e["kind"]: e for e in out["entry_points"]}
        assert (got["console-script"]["name"], got["console-script"]["target"], got["console-script"]["line"]) == (
            "shopcart", "shopcart.cli:main", py_repo.line_of("pyproject.toml", "ep-script"))
        assert (got["main-module"]["path"], got["main-module"]["line"], got["main-module"]["name"]) == (
            "src/shopcart/__main__.py", py_repo.line_of("src/shopcart/__main__.py", "ep-main-module"), "shopcart")

    def test_test_configs_are_in_the_tests_output(self, py_repo, tmp_path):
        out = py_adapter.PythonAdapter().extract(context(py_repo, tmp_path))

        assert {t["tool"] for t in out["tests"] if t["kind"] == "config"} == {"pytest", "coverage"}


class TestDead:
    def test_vulture_items_get_a_rule_and_a_snippet(self, py_repo, tmp_path):
        FakeVulture.items = [{"path": "src/shopcart/core.py", "line": 20, "end_line": 21, "name": "unused_helper", "type": "function",
                              "confidence": 60, "message": "unused function 'unused_helper'"}]

        out = py_adapter.PythonAdapter().extract(context(py_repo, tmp_path))

        assert [(d["rule"], d["snippet"]) for d in out["dead"]] == [("vulture.function", "unused_helper")]


class TestRegistration:
    def test_both_adapters_are_registered_and_the_repo_one_matches_any_language(self):
        names = [type(a).__name__ for a in adapters.detect(["Shell"])]

        assert names == ["RepoAdapter"]

    def test_python_matches_python(self):
        assert [type(a).__name__ for a in adapters.detect(["Python"])] == ["PythonAdapter", "RepoAdapter"]


class TestHandlerArgument:
    def test_the_handler_follows_the_command_name(self):
        found = py_adapter.HANDLER_ARG.search("init = add('init', cmd_init, 'write an example config file')")

        assert found.group(1) == "cmd_init"

    def test_a_call_with_a_computed_name_has_no_handler(self):
        assert py_adapter.HANDLER_ARG.search("add(name, handler, help)") is None

    def test_both_command_rules_are_registered_by_call(self):
        assert py_adapter.CALL_COMMAND_RULES == {"dossier.python.entry.argparse-subcommand", "dossier.python.entry.cli-helper-command"}


class TestComplexityOnModules:
    def test_adapter_version_is_3_so_old_extracts_are_not_reused(self):
        assert py_adapter.PythonAdapter.version == "3"


PYPROJECT = '[project]\nname = "{name}"\n[project.scripts]\n{name} = "app.main:main"\n'


def nested_context(tmp_path, venv_in=None):
    repo = tmp_path / "mixed"
    for rel, text in {"tool.py": "print('x')\n", "backend/pyproject.toml": PYPROJECT.format(name="backend"),
                      "backend/app/__init__.py": "", "backend/app/models.py": "X = 1\n", "backend/app/main.py": "def main(): pass\n",
                      "frontend/package.json": "{}\n"}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    if venv_in:
        (repo / venv_in / ".venv").mkdir(parents=True)
    tree = frozenset(p.relative_to(repo).as_posix() for p in repo.rglob("*") if p.is_file() and ".venv" not in p.parts)
    files = sorted(p for p in tree if p.endswith(".py"))
    return SimpleNamespace(checkout=repo, sha="a" * 40, tree=tree, files=files, area=tmp_path / "area", restored={}, run=None,
                           treesitter=FakeTS(), semgrep=FakeSemgrep(), tool_versions={"scip-python": "0.6.6"}, trusted=True,
                           repo_name="mixed", tool_status={})


def nested_graph(repo):
    app = str(Path(repo) / "backend" / "app")
    return {"modules": [{"module": "app", "path": app + "/__init__.py", "is_package": True},
                        {"module": "app.models", "path": app + "/models.py", "is_package": False},
                        {"module": "app.main", "path": app + "/main.py", "is_package": False}],
            "imports": [{"from": "app.main", "to": "app.models", "lines": [1]}], "contracts": [], "errors": []}


class TestProjects:
    def test_grimp_gets_roots_under_the_project_and_modules_keep_python_names(self, tmp_path):
        ctx = nested_context(tmp_path)
        FakeGrimp.response = nested_graph(ctx.checkout)

        out = py_adapter.PythonAdapter().extract(ctx)

        roots, packages, _ = FakeGrimp.all[0]
        assert roots == [str(ctx.checkout / "backend")] and packages == ["app"]
        modules = {(g["module"], g["path"]) for g in out["graph"] if g["kind"] == "module" and g["package"]}
        assert modules == {("app", "backend/app/__init__.py"), ("app.models", "backend/app/models.py"), ("app.main", "backend/app/main.py")}
        assert ctx.tool_status["grimp"]["status"] == "ok"

    def test_nested_items_carry_the_project_and_root_items_do_not(self, tmp_path):
        ctx = nested_context(tmp_path)
        FakeGrimp.response = nested_graph(ctx.checkout)

        out = py_adapter.PythonAdapter().extract(ctx)

        modules = [g for g in out["graph"] if g["kind"] == "module"]
        assert {g.get("project") for g in modules if g["path"].startswith("backend/")} == {"backend"}
        assert "project" not in next(g for g in modules if g["path"] == "tool.py")
        assert [g["module"] for g in modules if g["path"] == "tool.py"] == ["tool"]

    def test_console_scripts_cite_the_project_manifest(self, tmp_path):
        ctx = nested_context(tmp_path)

        out = py_adapter.PythonAdapter().extract(ctx)

        scripts = [e for e in out["entry_points"] if e["kind"] == "console-script"]
        assert [(e["name"], e["path"], e["project"]) for e in scripts] == [("backend", "backend/pyproject.toml", "backend")]

    def test_vulture_runs_per_project_on_its_own_paths(self, tmp_path):
        ctx = nested_context(tmp_path)

        py_adapter.PythonAdapter().extract(ctx)

        assert sorted(FakeVulture.calls, key=len) == [["tool.py"], ["backend/app/__init__.py", "backend/app/main.py", "backend/app/models.py"]]

    def test_scip_python_runs_in_the_project_folder_with_its_own_name(self, tmp_path, monkeypatch):
        ctx = nested_context(tmp_path, venv_in="backend")
        calls = []
        index = tmp_path / "index.scip"
        index.write_bytes(b"")
        monkeypatch.setattr(py_adapter.shutil, "which", lambda *a, **k: "/usr/bin/node")
        monkeypatch.setattr(scip_tool, "ensure_installed", lambda *a, **k: "/tool/index.js")
        monkeypatch.setattr(scip_tool, "run_index", lambda *a, **k: calls.append(k) or index)
        monkeypatch.setattr(scip_read, "reduce", lambda decoded: [{"kind": "def", "path": "app/models.py", "line": 1, "name": "X"}])

        out = py_adapter.PythonAdapter().extract(ctx)

        nested = next(c for c in calls if c.get("cwd"))
        assert nested["cwd"] == ctx.checkout / "backend" and nested["project_name"] == "mixed-backend"
        assert nested["venv"] == ctx.checkout / "backend" / ".venv"
        assert {s["path"] for s in out["symbols"]} == {"app/models.py", "backend/app/models.py"}

    def test_scip_python_uses_the_root_venv_when_the_project_has_none(self, tmp_path, monkeypatch):
        ctx = nested_context(tmp_path, venv_in="")
        calls = []
        index = tmp_path / "index.scip"
        index.write_bytes(b"")
        monkeypatch.setattr(py_adapter.shutil, "which", lambda *a, **k: "/usr/bin/node")
        monkeypatch.setattr(scip_tool, "ensure_installed", lambda *a, **k: "/tool/index.js")
        monkeypatch.setattr(scip_tool, "run_index", lambda *a, **k: calls.append(k) or index)
        monkeypatch.setattr(scip_read, "reduce", lambda decoded: [])

        py_adapter.PythonAdapter().extract(ctx)

        assert next(c for c in calls if c.get("cwd"))["venv"] == ctx.checkout / ".venv"

    def test_tool_status_keeps_ok_when_one_project_has_nothing_to_graph(self, tmp_path):
        ctx = nested_context(tmp_path)
        FakeGrimp.response = nested_graph(ctx.checkout)

        py_adapter.PythonAdapter().extract(ctx)

        assert ctx.tool_status["grimp"] == {"status": "ok", "reason": None}

    def test_a_failure_in_any_project_marks_the_tool_failed(self, tmp_path):
        ctx = nested_context(tmp_path)
        FakeGrimp.error = ToolError("boom")

        py_adapter.PythonAdapter().extract(ctx)

        assert ctx.tool_status["grimp"] == {"status": "failed", "reason": "boom"}
