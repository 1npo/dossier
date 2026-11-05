import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent / "scripts"))
import schema  # noqa: E402

PROMPTS = Path(__file__).resolve().parents[3] / "prompts"
RETIRED = re.compile(r"capabilities|code-tour|domain-logic|delivery|interfaces\b|architecture\b")


def json_after(text: str, heading: str) -> dict:
    """The first fenced json block after a `## heading` line."""
    tail = text.split(f"## {heading}", 1)[1]
    return json.loads(re.search(r"```json\n(.*?)\n```", tail, re.S).group(1))


def schema_for(report: dict) -> tuple:
    rid = report["cards"][0]["card"].split(".")[0]
    return rid, schema.load(rid)


class TestMethodExamples:
    method = (PROMPTS / "method.md").read_text(encoding="utf-8")

    def test_report_file_example_passes_the_card_schema(self):
        rep = json_after(self.method, "Report file shape: cards")
        rid, sch = schema_for(rep)

        errors, _ = schema.validate(rid, rep, sch, allow_pending=False)

        assert errors == []

    def test_tool_findings_example_passes_the_card_schema(self):
        rep = json_after(self.method, "Tool findings: keep, merge, dismiss")
        rid, sch = schema_for(rep)

        errors, _ = schema.validate(rid, rep, sch, allow_pending=False)

        assert errors == []

    def test_no_retired_report_name_appears(self):
        assert RETIRED.findall(self.method) == []


class TestReportsGuide:
    guide = (PROMPTS / "reports.md").read_text(encoding="utf-8")
    written = ("entry", "components", "interactions", "io", "data", "behavior", "conventions", "ops", "change", "contributors", "reading")

    def test_every_card_written_by_claude_is_described(self):
        ids = [c["id"] for rid in self.written for c in schema.load(rid)["cards"] if c["writer"] == "claude"]

        missing = [i for i in ids if f"(`{i}`)" not in self.guide]

        assert missing == []

    def test_cards_drawn_by_code_are_marked_not_to_be_written(self):
        ids = [c["id"] for rid in self.written for c in schema.load(rid)["cards"] if c["writer"] == "script"]

        for card_id in ids:
            section = self.guide.split(f"(`{card_id}`)", 1)[1].split("###", 1)[0]
            assert "Do not write this card" in section

    def test_no_retired_report_name_is_a_section_heading(self):
        headings = re.findall(r"^## (.+)$", self.guide, re.M)

        assert [h for h in headings if RETIRED.search(h)] == []
        assert "capabilities" not in headings

    def test_sections_follow_the_writing_order(self):
        headings = re.findall(r"^## (.+)$", self.guide, re.M)

        assert headings == [*self.written, "overview", "risks", "gaps", "corrections"]


class TestCompleteness:
    @pytest.fixture
    def both(self):
        return (PROMPTS / "method.md").read_text() + (PROMPTS / "reports.md").read_text()

    @pytest.mark.parametrize("phrase", ["short report", "smallest report", "6 to 10 nodes", "A short report is fine"])
    def test_prompt_does_not_ask_for_short_reports_or_small_diagrams(self, both, phrase):
        assert phrase not in both

    def test_merging_is_limited_to_call_sites(self, both):
        assert "Never merge entities (`md-`) or entry points (`ep-`)" in both

    def test_each_cli_command_and_environment_variable_gets_a_row(self, both):
        assert "one row per command" in both and "one row per environment variable" in both

    def test_recipes_cite_a_commit_or_say_unknown(self, both):
        assert "[[commit:<sha>]]" in both and "`unknown` with a note" in both

    def test_diagrams_are_split_not_trimmed(self, both):
        assert "never leave a step out" in both


class TestChangeAndContributorsGuide:
    guide = (PROMPTS / "reports.md").read_text(encoding="utf-8")
    method = (PROMPTS / "method.md").read_text(encoding="utf-8")

    def test_every_card_of_both_reports_is_described(self):
        ids = [c["id"] for rid in ("change", "contributors") for c in schema.load(rid)["cards"]]

        assert [i for i in ids if f"(`{i}`)" not in self.guide] == []

    def test_neither_report_is_called_unwritten(self):
        assert "not written in this version" not in self.guide + self.method

    def test_the_writing_order_puts_change_and_contributors_before_reading_and_risks_last(self):
        line = next(l for l in self.guide.splitlines() if l.startswith("**Write the reports in this order"))

        assert line.index("`ops`") < line.index("`change`") < line.index("`contributors`") < line.index("`reading`") < line.index("`risks`")

    def test_the_status_words_and_the_unknown_owner_rule_are_given(self):
        section = self.guide.split("(`contributors.concentration`)", 1)[1].split("###", 1)[0]

        assert "`single owner`, `departed` or `shared`" in section and "`inferred`" in section and "`unknown`" in section

    def test_a_group_id_may_decide_markers(self):
        section = self.guide.split("(`change.decisions`)", 1)[1].split("###", 1)[0]

        assert "group id" in section and "`unknown`" in section

    def test_contract_directions_are_exactly_offered_or_consumed(self):
        assert "exactly `offered`" in self.guide and "`consumed`" in self.guide

    def test_risks_gain_the_source_column_with_its_two_values(self):
        section = self.guide.split("## risks", 1)[1]

        assert "`Source`" in section and "`extractor`" in section and "`read`" in section

    def test_people_are_written_by_display_name(self):
        assert "never email addresses" in self.guide

    def test_history_is_a_citation_key_and_v8_is_listed(self):
        assert "`history`" in self.method and "V8" in self.method
