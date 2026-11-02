import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent / "scripts"))

import buildlog  # noqa: E402
import dossier  # noqa: E402
import page_audit  # noqa: E402


@pytest.fixture
def out(tmp_path, monkeypatch):
    out = tmp_path / "home" / "demo"
    (out / "reports").mkdir(parents=True)
    (out / "dossier-demo.html").write_text("<html><body></body></html>")
    monkeypatch.setattr(dossier, "toplevel", lambda repo: str(tmp_path / "repo"))
    monkeypatch.setattr(dossier, "out_dir", lambda top: (out, "demo", "abc"))
    return out


def stub(monkeypatch, audit=(), code=0, text='{"diagrams_checked": 3, "problems": 0}\n'):
    calls = []
    monkeypatch.setattr(page_audit, "audit", lambda *a, **kw: list(audit))
    monkeypatch.setattr(dossier, "run_browser_check", lambda html, out: (calls.append(html), (code, text))[1])
    return calls


def run_check(capsys, repo="."):
    with pytest.raises(SystemExit) as exit_:
        dossier.cmd_check(type("A", (), {"repo": repo})())
    return exit_.value.code, capsys.readouterr().out


class TestCmdCheck:
    def test_a_clean_page_prints_zero_problems_and_exits_zero(self, out, monkeypatch, capsys):
        stub(monkeypatch)

        code, text = run_check(capsys)

        assert code == 0 and text.strip().endswith("problems: 0")

    def test_page_audit_errors_are_printed_and_counted(self, out, monkeypatch, capsys):
        stub(monkeypatch, audit=["V11: data.entities: table 1 has 2 rows, expected 3."])

        code, text = run_check(capsys)

        assert code == 1 and "FAIL V11: data.entities: table 1 has 2 rows, expected 3." in text and text.strip().endswith("problems: 1")

    def test_browser_failures_are_counted_from_its_fail_lines(self, out, monkeypatch, capsys):
        stub(monkeypatch, code=1, text='{"diagrams_checked": 3, "problems": 2}\nFAIL [light] a\nFAIL [dark] b\n')

        code, text = run_check(capsys)

        assert code == 1 and text.strip().endswith("problems: 2")

    def test_a_browser_check_that_crashed_is_one_problem_not_a_pass(self, out, monkeypatch, capsys):
        stub(monkeypatch, code=2, text="uv: could not start\n")

        code, text = run_check(capsys)

        assert code == 1 and text.strip().endswith("problems: 1")

    def test_both_checks_add_up(self, out, monkeypatch, capsys):
        stub(monkeypatch, audit=["V11: x"], code=1, text="FAIL [light] a\n")

        _, text = run_check(capsys)

        assert text.strip().endswith("problems: 2")

    def test_the_browser_check_runs_on_the_page_in_the_dossier_folder(self, out, monkeypatch, capsys):
        calls = stub(monkeypatch)

        run_check(capsys)

        assert calls == [out / "dossier-demo.html"]

    def test_no_page_says_to_render_first(self, out, monkeypatch, capsys):
        (out / "dossier-demo.html").unlink()
        stub(monkeypatch)

        with pytest.raises(SystemExit) as exit_:
            dossier.cmd_check(type("A", (), {"repo": "."})())

        assert exit_.value.code == 1 and "Run render first" in capsys.readouterr().err


class TestBrowserCheckLine:
    def test_no_record_is_not_run(self):
        assert dossier.browser_check_line({"records": []}) == "not run"

    def test_no_build_is_not_run(self):
        assert dossier.browser_check_line(None) == "not run"

    def test_a_record_says_how_many_problems_and_when(self):
        rec = {"step": "check", "part": "browser", "by": "check_page", "status": "ok", "counts": {"problems": 0}, "started": "2026-11-02T10:04:05Z"}

        assert dossier.browser_check_line({"records": [rec]}) == "0 problems at 2026-11-02 10:04 UTC"

    def test_one_problem_is_singular(self):
        rec = {"step": "check", "part": "browser", "by": "check_page", "status": "failed", "reason": "x", "counts": {"problems": 1}, "started": "2026-11-02T10:04:05Z"}

        assert dossier.browser_check_line({"records": [rec]}).startswith("1 problem at")


def test_render_summary_says_the_browser_check_was_not_run_on_a_fresh_build(tmp_path):
    build = buildlog.start(tmp_path, repo="r", sha="a" * 40, ref="main", version="0.7.1", options={})

    assert dossier.browser_check_line(buildlog.load(build)) == "not run"
