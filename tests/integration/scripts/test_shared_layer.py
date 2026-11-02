import functools
import os
from pathlib import Path

import pytest

import sandbox
import shared_tools

SKILL = Path(__file__).resolve().parents[2].parent
FIXTURE_RULES = Path(__file__).resolve().parents[2] / "fixtures" / "rules"

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")


@pytest.fixture
def project(tmp_path):
    area = tmp_path / "cache" / "repo"
    work = tmp_path / "work"
    area.mkdir(parents=True)
    work.mkdir()
    (work / "a.py").write_text('print("x")\nlen([])\n')
    return functools.partial(sandbox.run, area=area, cwd=work, timeout=600)


class TestSharedLayer:
    def test_treesitter_finds_both_calls(self, project):
        got = shared_tools.TreeSitter(project).query("python", ["a.py"], "(call function: (identifier) @fn)")

        assert [m["text"] for m in got] == ["print", "len"]

    def test_semgrep_finds_the_print_call(self, project):
        got = shared_tools.Semgrep(project).scan(FIXTURE_RULES)

        assert [(r["rule"], r["start_line"]) for r in got] == [("dossier.test.io.print-call", 1)]


class TestSemgrepRules:
    def test_every_shipped_rule_passes_its_semgrep_test_file(self, project):
        got = shared_tools.Semgrep(project).test(SKILL / "rules", SKILL / "tests" / "fixtures" / "semgrep")

        assert got["returncode"] == 0, got["output"]

    def test_scan_reads_the_snippet_and_detail_from_the_source(self, project, tmp_path):
        rules = tmp_path / "rules"
        rules.mkdir()
        (rules / "r.yml").write_text(
            "rules:\n  - id: dossier.test.env\n    pattern: os.getenv(...)\n    languages: [python]\n    severity: INFO\n"
            "    message: m\n    metadata: {detail: '[(]\\s*[\"'']([^\"'']+)[\"'']'}\n")
        work = tmp_path / "work"
        (work / "e.py").write_text("import os\n\nkey = os.getenv('SHOP_KEY')\n")

        got = shared_tools.Semgrep(project).scan(rules, ["e.py"])

        assert [(r["start_line"], r["snippet"], r["detail"]) for r in got] == [(3, "key = os.getenv('SHOP_KEY')", "SHOP_KEY")]
