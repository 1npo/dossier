import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import semgrep_worker
import shared_tools
import toolcheck

SCRIPTS = Path(shared_tools.__file__).parent


def fake_run(tmp_path, response=None, returncode=0, stderr="", timed_out=False):
    calls = []

    def run(cmd, *, input, stage, profile):
        out, err = tmp_path / "o", tmp_path / "e"
        out.write_text(json.dumps(response or {}))
        err.write_text(stderr)
        calls.append({"cmd": cmd, "input": json.loads(input), "stage": stage, "profile": profile})
        return SimpleNamespace(returncode=returncode, stdout=out, stderr=err, timed_out=timed_out)

    run.calls = calls
    return run


class TestTreeSitter:
    def test_sends_the_request_and_returns_matches(self, tmp_path):
        run = fake_run(tmp_path, {"matches": [{"path": "a.py", "capture": "fn", "text": "print"}], "errors": []})

        got = shared_tools.TreeSitter(run).query("python", ["a.py"], "(call) @fn")

        assert got == [{"path": "a.py", "capture": "fn", "text": "print"}]
        call = run.calls[0]
        assert call["input"] == {"language": "python", "paths": ["a.py"], "query": "(call) @fn"}
        assert (call["stage"], call["profile"]) == ("treesitter", "tool")
        assert call["cmd"][:5] == ["uv", "run", "--locked", "--python", "3.13"]

    def test_nonzero_exit_raises_with_stderr_tail(self, tmp_path):
        run = fake_run(tmp_path, returncode=2, stderr="\n".join(f"line {i}" for i in range(30)))

        with pytest.raises(shared_tools.ToolError, match="line 29") as e:
            shared_tools.TreeSitter(run).query("python", [], "q")

        assert "line 5" not in str(e.value)

    def test_timeout_raises(self, tmp_path):
        run = fake_run(tmp_path, timed_out=True, returncode=None)

        with pytest.raises(shared_tools.ToolError, match="took too long"):
            shared_tools.TreeSitter(run).query("python", [], "q")


class TestSemgrep:
    def test_sends_absolute_config_and_returns_results(self, tmp_path):
        run = fake_run(tmp_path, {"results": [{"rule": "r", "path": "a.py"}], "errors": []})

        got = shared_tools.Semgrep(run).scan(tmp_path, ["a.py"], timeout=7)

        assert got == [{"rule": "r", "path": "a.py"}]
        assert run.calls[0]["input"] == {"config": str(tmp_path.resolve()), "paths": ["a.py"], "timeout": 7}
        assert run.calls[0]["stage"] == "semgrep"

    def test_nonzero_exit_raises(self, tmp_path):
        run = fake_run(tmp_path, returncode=2, stderr="bad rules")

        with pytest.raises(shared_tools.ToolError, match="bad rules"):
            shared_tools.Semgrep(run).scan(tmp_path)


class TestWorkerPins:
    @pytest.mark.parametrize("worker,tool", [("ts_worker.py", "tree-sitter-language-pack"), ("semgrep_worker.py", "semgrep")])
    def test_pin_matches_tools_json(self, worker, tool):
        text = (SCRIPTS / worker).read_text()
        pinned = re.search(rf'dependencies = \["{re.escape(tool)}==([^"]+)"\]', text).group(1)
        listed = next(t["version"] for t in toolcheck.load_tools()["tools"] if t["id"] == tool)

        assert pinned == listed

    @pytest.mark.parametrize("worker", ["ts_worker.py", "semgrep_worker.py"])
    def test_worker_is_locked(self, worker):
        assert (SCRIPTS / f"{worker}.lock").exists()


class TestRuleId:
    def test_strips_the_config_folder_prefix(self):
        got = semgrep_worker.rule_id("tmp.rules.python.dossier.python.io.print", "/tmp/rules")

        assert got == "dossier.python.io.print"

    def test_keeps_an_unprefixed_id(self):
        assert semgrep_worker.rule_id("dossier.a.b", "/x") == "dossier.a.b"
