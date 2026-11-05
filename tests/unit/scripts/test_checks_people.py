import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import checks_people  # noqa: E402

COLUMNS = ["ID", "Risk", "Category", "Severity", "Impact", "Recommendation", "Source"]


def risks(*sources):
    rows = [{"cells": [f"R{i}", "r", "c", "high", "i", "do", s], "conf": "confirmed", "cite": ["a.py"]} for i, s in enumerate(sources)]
    return {"risks": {"cards": [{"card": "risks.tracker", "blocks": [{"type": "table", "columns": COLUMNS, "rows": rows}]}]}}


class TestRiskSource:
    def test_extractor_and_read_are_accepted(self):
        assert checks_people.risk_source(risks("extractor", "read")) == []

    def test_other_words_are_named(self):
        assert checks_people.risk_source(risks("read", "guess")) == ["V5: Risks: Source must be extractor or read, found 'guess'."]

    def test_an_empty_cell_is_an_error(self):
        assert checks_people.risk_source(risks("")) == ["V5: Risks: Source must be extractor or read, found ''."]

    def test_a_card_marked_not_applicable_is_skipped(self):
        reports = {"risks": {"cards": [{"card": "risks.tracker", "na": "x", "cite": ["a"]}]}}

        assert checks_people.risk_source(reports) == []

    def test_no_risks_report_is_skipped(self):
        assert checks_people.risk_source({}) == []
