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

    def test_files_the_worker_skipped_are_kept_on_the_client(self, tmp_path):
        run = fake_run(tmp_path, {"matches": [], "errors": [{"path": "a.py", "error": "tree-sitter stopped on this file (signal 11); it was skipped"}]})
        client = shared_tools.TreeSitter(run)

        client.query("python", ["a.py"], "(call) @fn")

        assert client.skipped == {"a.py": "tree-sitter stopped on this file (signal 11); it was skipped"}

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


class TestPyWorkerPins:
    def test_dependencies_name_the_tools_json_versions_of_grimp_and_vulture(self):
        text = (SCRIPTS / "py_worker.py").read_text()
        pins = dict(re.findall(r'"([a-z-]+)==([^"]+)"', re.search(r"dependencies = \[(.*)\]", text).group(1)))
        listed = {t["id"]: t["version"] for t in toolcheck.load_tools()["tools"] if t["id"] in ("grimp", "vulture")}

        assert pins == listed

    def test_worker_is_locked(self):
        assert (SCRIPTS / "py_worker.py.lock").exists()


class TestSemgrepTest:
    def test_sends_the_test_request_with_absolute_paths(self, tmp_path):
        run = fake_run(tmp_path, {"returncode": 0, "output": "ok"})

        got = shared_tools.Semgrep(run).test(tmp_path, tmp_path)

        assert got == {"returncode": 0, "output": "ok"}
        assert run.calls[0]["input"] == {"test": True, "config": str(tmp_path.resolve()), "targets": str(tmp_path.resolve())}


class TestWorkerText:
    def test_matched_text_is_read_between_byte_offsets(self, tmp_path, monkeypatch):
        (tmp_path / "a.py").write_text("x = os.getenv('K')\n")
        monkeypatch.chdir(tmp_path)

        assert semgrep_worker.matched_text("a.py", 4, 18) == "os.getenv('K')"

    def test_unreadable_file_gives_empty_text(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        assert semgrep_worker.matched_text("missing.py", 0, 5) == ""

    def test_source_line_is_the_stripped_line_where_the_match_starts(self, tmp_path, monkeypatch):
        (tmp_path / "a.py").write_text("import os\n    key = os.getenv('K')\n")
        monkeypatch.chdir(tmp_path)

        assert semgrep_worker.source_line("a.py", 2) == "key = os.getenv('K')"

    def test_source_line_is_cut_at_200_characters(self, tmp_path, monkeypatch):
        (tmp_path / "a.py").write_text("a" * 500 + "\n")
        monkeypatch.chdir(tmp_path)

        assert len(semgrep_worker.source_line("a.py", 1)) == 200

    def test_source_line_past_the_end_or_unreadable_is_empty(self, tmp_path, monkeypatch):
        (tmp_path / "a.py").write_text("x\n")
        monkeypatch.chdir(tmp_path)

        assert (semgrep_worker.source_line("a.py", 9), semgrep_worker.source_line("nope.py", 1)) == ("", "")

    def test_detail_is_the_first_group(self):
        assert semgrep_worker.detail_of("os.environ.get('SHOP_DB', 'x')", r"[(\[]\s*[\"']([^\"']+)[\"']") == "SHOP_DB"

    def test_detail_without_a_pattern_is_none(self):
        assert semgrep_worker.detail_of("x", None) is None

    def test_detail_with_no_match_is_none(self):
        assert semgrep_worker.detail_of("x", r"(zzz)") is None

    def test_detail_with_a_bad_pattern_is_none(self):
        assert semgrep_worker.detail_of("x", "(") is None


class TestChunked:
    def test_paths_are_split_into_batches(self):
        assert semgrep_worker.chunked(["a", "b", "c"], 2) == [["a", "b"], ["c"]]

    def test_no_paths_give_one_empty_batch_so_the_current_directory_is_scanned(self):
        assert semgrep_worker.chunked(None) == [[]] and semgrep_worker.chunked([]) == [[]]

    def test_a_long_list_stays_under_the_batch_size(self):
        batches = semgrep_worker.chunked([str(i) for i in range(1000)])

        assert all(len(b) <= semgrep_worker.CHUNK for b in batches) and sum(map(len, batches)) == 1000
