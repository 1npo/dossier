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


def person(name, kind="human", aliases=()):
    return {"kind": "person", "person": name.lower() + "@x", "name": name, "type": kind, "aliases": list(aliases)}


CATALOG = [{"name": "Core", "paths": ["src/"]}, {"name": "Web", "paths": ["web/"]}]


def card(cid, columns, *rows, conf="inferred"):
    return {"card": cid, "blocks": [{"type": "table", "columns": columns, "rows": [{"cells": list(r), "conf": conf, "cite": ["a.py"]} for r in rows]}]}


def good(**over):
    cards = {
        "contributors.people": card("contributors.people", ["Person", "Role", "Areas", "Active?"], ("Ann", "lead", "Core", "yes"), ("Bob", "dev", "Web", "yes")),
        "contributors.ask": card("contributors.ask", ["Subsystem", "Ask first", "Then", "Basis"], ("Core", "Ann", "Bob", "x"), ("Web", "Bob", "Ann", "x")),
        "contributors.concentration": card("contributors.concentration", ["Area", "Owner", "Share", "Status"],
                                           ("Core", "Ann", "-", "shared"), ("Web", "Bob", "-", "single owner")),
        "contributors.agents": card("contributors.agents", ["Identity", "Kind", "Areas touched", "Share of commits"], ("Claude", "agent", "-", "-")),
        "contributors.doubts": {"card": "contributors.doubts", "na": "none", "cite": ["a.py"]}}
    cards.update(over)
    return {"contributors": {"cards": list(cards.values())}}


def extract(*extra):
    return {"history": [person("Ann"), person("Bob"), person("Claude", "agent"), *extra]}


def run(reports=None, ext=None):
    return checks_people.people(reports or good(), ext or extract(), CATALOG)


class TestPeople:
    def test_a_complete_report_has_no_errors(self):
        assert run() == []

    def test_a_missing_human_is_named(self):
        reports = good(**{"contributors.people": card("contributors.people", ["Person", "Role", "Areas", "Active?"], ("Ann", "lead", "Core", "yes"))})

        assert run(reports) == ["V5: Who the people are does not list Bob."]

    def test_a_human_in_the_doubts_card_counts_as_listed(self):
        reports = good(**{"contributors.people": card("contributors.people", ["Person", "Role", "Areas", "Active?"], ("Ann", "lead", "Core", "yes")),
                          "contributors.doubts": card("contributors.doubts", ["Identity", "Doubt", "What would settle it"], ("Bob", "maybe a bot", "ask"))})

        assert run(reports) == []

    def test_a_missing_agent_and_a_missing_assistant_are_named(self):
        reports = good(**{"contributors.agents": {"card": "contributors.agents", "na": "none", "cite": ["a.py"]}})
        ext = extract({"kind": "assistant", "name": "Copilot", "commits": 1, "files": {}})

        assert run(reports, ext) == ["V5: Agents and bots does not list Claude.", "V5: Agents and bots does not list Copilot."]

    def test_a_missing_component_is_named_in_both_cards(self):
        reports = good(**{"contributors.ask": card("contributors.ask", ["Subsystem", "Ask first", "Then", "Basis"], ("Core", "Ann", "Bob", "x")),
                          "contributors.concentration": card("contributors.concentration", ["Area", "Owner", "Share", "Status"], ("Web", "Bob", "-", "shared"),
                                                             ("Core", "Ann", "-", "shared"))})

        assert run(reports) == ["V5: Who to ask has no row for the component Web."]

    def test_a_name_that_is_nobody_in_this_build_is_named(self):
        reports = good(**{"contributors.people": card("contributors.people", ["Person", "Role", "Areas", "Active?"], ("Ann", "l", "c", "y"), ("Bob", "d", "w", "y"),
                                                      ("Zed", "d", "w", "y"))})

        assert run(reports) == ["V5: Who the people are names Zed, which is not an identity in this build."]

    def test_an_unknown_component_name_is_named(self):
        reports = good(**{"contributors.ask": card("contributors.ask", ["Subsystem", "Ask first", "Then", "Basis"], ("Core", "Ann", "Bob", "x"),
                                                   ("Web", "Bob", "Ann", "x"), ("Moon", "Ann", "Bob", "x"))})

        assert run(reports) == ["V5: Who to ask names Moon, which is not a component in this build."]

    def test_an_owner_who_is_nobody_is_named(self):
        reports = good(**{"contributors.concentration": card("contributors.concentration", ["Area", "Owner", "Share", "Status"],
                                                             ("Core", "Zed", "-", "shared"), ("Web", "Bob", "-", "shared"))})

        assert run(reports) == ["V5: Knowledge concentration names Zed, which is not an identity in this build."]

    def test_an_unrecognised_status_is_reported(self):
        reports = good(**{"contributors.concentration": card("contributors.concentration", ["Area", "Owner", "Share", "Status"],
                                                             ("Core", "Ann", "-", "mine"), ("Web", "Bob", "-", "shared"))})

        assert run(reports) == ["V5: Knowledge concentration, Core: Status must be single owner, departed or shared."]

    def test_on_a_one_human_project_naming_anyone_else_is_reported(self):
        ext = {"history": [person("Ann"), person("Claude", "agent")]}
        reports = good(**{"contributors.people": card("contributors.people", ["Person", "Role", "Areas", "Active?"], ("Ann", "l", "c", "y")),
                          "contributors.concentration": card("contributors.concentration", ["Area", "Owner", "Share", "Status"],
                                                             ("Core", "Claude", "-", "shared"), ("Web", "Ann", "-", "shared"))})
        reports["contributors"]["cards"][1] = card("contributors.ask", ["Subsystem", "Ask first", "Then", "Basis"], ("Core", "Ann", "-", "x"), ("Web", "Ann", "-", "x"))

        assert run(reports, ext) == ["V5: Knowledge concentration, Core: Ann is the only person on this project, so they are the owner."]

    def test_an_unknown_owner_is_accepted_only_with_conf_unknown(self):
        ok = card("contributors.concentration", ["Area", "Owner", "Share", "Status"], ("Core", "unknown", "-", "shared"), ("Web", "Bob", "-", "shared"), conf="unknown")
        bad = card("contributors.concentration", ["Area", "Owner", "Share", "Status"], ("Core", "unknown", "-", "shared"), ("Web", "Bob", "-", "shared"))

        assert run(good(**{"contributors.concentration": ok})) == []
        assert run(good(**{"contributors.concentration": bad})) == ["V5: Knowledge concentration, Core: an Owner of unknown needs conf unknown."]

    def test_a_pending_card_is_left_to_v6(self):
        reports = good(**{"contributors.people": {"card": "contributors.people", "pending": True}})

        assert run(reports) == []

    def test_no_history_is_left_alone(self):
        assert run(ext={}) == []

    def test_citations_in_a_cell_are_ignored_when_matching(self):
        reports = good(**{"contributors.people": card("contributors.people", ["Person", "Role", "Areas", "Active?"], ("Ann [[a.py:1]]", "l", "c", "y"), ("`Bob`", "d", "w", "y"))})

        assert run(reports) == []
