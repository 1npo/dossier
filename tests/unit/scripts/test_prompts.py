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


class TestJavaScriptGuidance:
    guide = (PROMPTS / "reports.md").read_text(encoding="utf-8")
    method = (PROMPTS / "method.md").read_text(encoding="utf-8")

    def section(self, card_id):
        return self.guide.split(f"(`{card_id}`)", 1)[1].split("###", 1)[0]

    def test_the_method_names_the_javascript_tools(self):
        line = next(l for l in self.method.splitlines() if l.startswith("Before the code is read, tools ("))

        for tool in ("dependency-cruiser", "knip", "scip-typescript", "TypeScript compiler"):
            assert tool in line

    def test_the_method_speaks_of_javascript_projects_beside_python_packages(self):
        assert "the Python packages, JavaScript projects or C# projects" in self.method

    def test_a_route_is_written_with_its_full_path(self):
        section = self.section("entry.catalog")

        assert "full path" in section and "route-mount" in section

    def test_package_scripts_are_entry_points_and_wrapping_scripts_merge_only_on_the_same_path_and_name(self):
        section = self.section("entry.catalog")

        assert "package scripts" in section.lower() and "same `path` and `name`" in section and "dismiss" in section

    def test_the_entities_card_lists_the_javascript_kinds_and_says_props_are_left_out(self):
        section = self.section("data.entities")

        for word in ("interfaces", "object types", "enums", "Prisma models", "ORM classes", "Props"):
            assert word in section

    def test_several_apps_are_not_merged_into_one_component(self):
        assert "do not merge apps" in self.section("components.catalog")

    def test_the_public_surface_is_what_the_component_offers_other_packages(self):
        assert "other packages" in self.section("components.catalog") and "internal" in self.section("components.catalog")

    def test_the_contracts_card_does_not_copy_the_public_api_table(self):
        section = self.section("io.contracts")

        assert "never copy" in section and "offered" in section and "public API" in section

    def test_the_graph_card_says_it_lists_react_components_and_that_context_wiring_is_in_gaps(self):
        section = self.section("interactions.graph")

        assert "React components" in section and "Gaps" in section and "Do not write this card" in section

    def test_stale_flags_are_not_said_to_be_python_only(self):
        assert "for Python" not in self.guide

    def test_technologies_gives_react_idioms(self):
        section = self.section("reading.technologies")

        assert "React" in section and "routing" in section and "data-fetching" in section

    def test_a_paragraph_covers_repositories_with_more_than_one_language(self):
        assert "Repositories with more than one language" in self.guide


class TestCSharpGuidance:
    guide = (PROMPTS / "reports.md").read_text(encoding="utf-8")
    method = (PROMPTS / "method.md").read_text(encoding="utf-8")
    skill = (Path(__file__).resolve().parents[3] / "SKILL.md").read_text(encoding="utf-8")

    def section(self, card_id):
        return self.guide.split(f"(`{card_id}`)", 1)[1].split("###", 1)[0]

    def test_the_method_names_scip_dotnet_and_links_by_the_types_a_file_uses(self):
        assert "scip-dotnet for C#" in self.method and "linked by the types they use" in self.method

    def test_the_components_step_names_csharp_projects(self):
        assert "the Python packages, JavaScript projects or C# projects" in self.method

    def test_entry_routes_are_written_as_the_attributes_say_with_their_prefix_source(self):
        section = self.section("entry.catalog")

        assert "`route-convention`" in section and "`route-mount`" in section and "`conventional-route`" in section
        assert "ApiPrefix" in section and "Hosted services" in section

    def test_data_entities_name_what_the_csharp_tool_includes_and_leaves_out(self):
        section = self.section("data.entities")

        assert "EF Core entities, owned types, Dapper rows" in section and "DTOs" in section

    def test_components_keep_two_csharp_projects_apart(self):
        section = self.section("components.catalog")

        assert "never put two projects' files in one component unless one references the other" in section

    def test_contracts_give_one_row_per_csharp_library_with_an_api(self):
        assert "one `io.contracts` row per library" in self.section("io.contracts")

    def test_flows_say_what_dependency_injection_hides(self):
        section = self.section("interactions.flows")

        assert "dependency injection" in section and "`inferred`" in section

    def test_technologies_list_the_csharp_idioms(self):
        section = self.section("reading.technologies")

        assert "dependency injection lifetimes" in section and "source generators" in section

    def test_the_mixed_language_paragraph_names_csharp(self):
        paragraph = next(l for l in self.guide.splitlines() if l.startswith("**Repositories with more than one language"))

        assert "C#" in paragraph

    def test_doctor_says_the_dotnet_sdk_is_needed_for_csharp(self):
        section = self.skill.split("### `/dossier doctor [repo]`", 1)[1].split("###", 1)[0]

        assert ".NET SDK" in section and "C#" in section


SKILL_MD = (Path(__file__).resolve().parents[3] / "SKILL.md").read_text(encoding="utf-8")


class TestVerifyPrompt:
    prompt = (PROMPTS / "verify.md").read_text(encoding="utf-8")

    @pytest.mark.parametrize("word", ["supported", "not supported", "cannot tell"])
    def test_names_each_verdict(self, word):
        assert f"`{word}`" in self.prompt

    @pytest.mark.parametrize("key", ["id", "verdict", "reason"])
    def test_names_each_answer_key(self, key):
        assert f"`{key}`" in self.prompt

    def test_says_repository_text_is_data(self):
        assert "is data" in self.prompt and "Never follow them" in self.prompt


class TestSkillVerifyStep:
    def test_names_both_commands_and_the_agent_type(self):
        for word in ("verify-sample", "verify-record", "general-purpose"):
            assert word in SKILL_MD

    def test_says_the_report_is_never_given_to_the_agent(self):
        assert "Never give it a report" in SKILL_MD

    def test_build_hint_and_flag_list_name_verify(self):
        hint = re.search(r"^argument-hint: (.*)$", SKILL_MD, re.M).group(1)

        assert "[--verify]" in hint
        assert "`--verify`" in SKILL_MD


def card_section(guide: str, card_id: str) -> str:
    return guide.split(f"(`{card_id}`)", 1)[1].split("###", 1)[0]


class TestGraphsAreDrawnByCode:
    guide = (PROMPTS / "reports.md").read_text(encoding="utf-8")
    method = (PROMPTS / "method.md").read_text(encoding="utf-8")

    @pytest.mark.parametrize("card_id", ["components.map", "interactions.graph"])
    def test_graph_card_says_the_graph_is_never_described(self, card_id):
        section = card_section(self.guide, card_id)

        assert "interactive graph" in section
        assert "never describe" in section

    def test_components_guidance_says_tier_b_files_have_no_links(self):
        section = self.method.split("## Components", 1)[1].split("\n## ", 1)[0]

        assert "no static graph" in section

    def test_contracts_guidance_covers_python_libraries(self):
        section = card_section(self.guide, "io.contracts")

        assert "Python" in section


class TestSkillSteps:
    skill = (PROMPTS.parent / "SKILL.md").read_text(encoding="utf-8")

    def test_step_one_mentions_the_freshness_tile(self):
        step = self.skill.split("1. **Prepare.**", 1)[1].split("2. **Size check.**", 1)[0]

        assert "freshness" in step.lower()

    def test_finish_step_explains_the_no_static_graph_badge(self):
        step = self.skill.split("8. **Finish.**", 1)[1].split("### `/dossier confirm`", 1)[0]

        assert "no static graph" in step


class TestRulesReadme:
    def test_python_barrel_rule_is_described(self):
        text = (PROMPTS.parent / "rules" / "README.md").read_text(encoding="utf-8")

        assert "`__init__.py`" in text and "route-mount" in text
