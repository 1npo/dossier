import json
from types import SimpleNamespace

import pytest

import py_tools
import py_worker
import shared_tools


def fake_run(tmp_path, response=None, returncode=0, stderr="", timed_out=False):
    calls = []

    def run(cmd, *, input, stage, profile, timeout=None):
        out, err = tmp_path / "o", tmp_path / "e"
        out.write_text(json.dumps(response or {}))
        err.write_text(stderr)
        calls.append({"cmd": cmd, "input": json.loads(input), "stage": stage, "profile": profile, "timeout": timeout})
        return SimpleNamespace(returncode=returncode, stdout=out, stderr=err, timed_out=timed_out)

    run.calls = calls
    return run


class TestGrimp:
    def test_sends_the_graph_request_with_the_timeout(self, tmp_path):
        run = fake_run(tmp_path, {"modules": [{"module": "p"}], "imports": [], "contracts": [], "errors": []})

        got = py_tools.Grimp(run, 90).graph(["/co/src"], ["p"], [{"name": "c"}])

        assert got["modules"] == [{"module": "p"}]
        call = run.calls[0]
        assert call["input"] == {"mode": "graph", "roots": ["/co/src"], "packages": ["p"], "contracts": [{"name": "c"}]}
        assert (call["stage"], call["profile"], call["timeout"]) == ("grimp", "tool", 90)
        assert call["cmd"][-1].endswith("py_worker.py")

    def test_errors_with_no_modules_raise(self, tmp_path):
        run = fake_run(tmp_path, {"modules": [], "imports": [], "contracts": [], "errors": ["No module named p"]})

        with pytest.raises(shared_tools.ToolError, match="No module named p"):
            py_tools.Grimp(run, 1).graph([], ["p"], [])

    def test_nonzero_exit_raises(self, tmp_path):
        run = fake_run(tmp_path, returncode=1, stderr="traceback here")

        with pytest.raises(shared_tools.ToolError, match="traceback here"):
            py_tools.Grimp(run, 1).graph([], ["p"], [])

    def test_timeout_raises(self, tmp_path):
        run = fake_run(tmp_path, timed_out=True, returncode=None)

        with pytest.raises(shared_tools.ToolError, match="took too long"):
            py_tools.Grimp(run, 1).graph([], ["p"], [])


class TestVulture:
    def test_sends_the_dead_request_and_returns_items(self, tmp_path):
        run = fake_run(tmp_path, {"items": [{"name": "unused", "line": 2}]})

        got = py_tools.Vulture(run, 60).dead(["a.py"], {"ignore_names": ["x"], "min_confidence": 80})

        assert got == [{"name": "unused", "line": 2}]
        assert run.calls[0]["input"] == {"mode": "dead", "paths": ["a.py"], "ignore_names": ["x"], "ignore_decorators": [],
                                         "min_confidence": 80}
        assert run.calls[0]["stage"] == "vulture"

    def test_nonzero_exit_raises(self, tmp_path):
        run = fake_run(tmp_path, returncode=2, stderr="bad input")

        with pytest.raises(shared_tools.ToolError, match="bad input"):
            py_tools.Vulture(run, 1).dead([], {})


class TestModulePath:
    def test_module_file_and_package_init_are_found(self, tmp_path):
        (tmp_path / "pkg" / "sub").mkdir(parents=True)
        (tmp_path / "pkg" / "__init__.py").write_text("")
        (tmp_path / "pkg" / "sub" / "__init__.py").write_text("")
        (tmp_path / "pkg" / "a.py").write_text("")

        got = [py_worker.module_path(n, [str(tmp_path)]) for n in ("pkg", "pkg.a", "pkg.sub", "pkg.nope")]

        assert got == [(str(tmp_path / "pkg" / "__init__.py"), True), (str(tmp_path / "pkg" / "a.py"), False),
                       (str(tmp_path / "pkg" / "sub" / "__init__.py"), True), (None, False)]


class TestLayerNames:
    def test_plain_layer_is_one_dependent_name(self):
        assert py_worker.layer_names("app.web") == (["app.web"], False)

    def test_pipe_makes_independent_siblings(self):
        assert py_worker.layer_names("a | b") == (["a", "b"], True)

    def test_colon_makes_siblings_that_may_import_each_other(self):
        assert py_worker.layer_names("a : b") == (["a", "b"], False)

    def test_parentheses_mark_an_optional_layer_and_are_dropped(self):
        assert py_worker.layer_names("(utils)") == (["utils"], False)
