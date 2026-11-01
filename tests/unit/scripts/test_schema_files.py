import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent / "scripts"))
import schema  # noqa: E402

PART1 = {"dossier", "overview", "reading", "entry", "components", "interactions", "risks", "gaps", "corrections"}


def test_files_lint_clean():
    allsch = schema.load_all()
    assert set(allsch) == PART1
    for stem, sch in allsch.items():
        assert stem in schema.REPORT_ORDER
        assert sch["report"] == stem
        assert isinstance(sch["question"], str) and sch["question"].strip()
        assert schema.lint(sch) == [], stem
