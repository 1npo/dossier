import sys
from pathlib import Path

from dossier.render.measured import people as measured_people  # noqa: E402
from people_items import CATALOG, META, person


def table_entry(columns, *rows):
    return {"card": "x", "blocks": [{"type": "table", "columns": columns, "rows": [{"cells": list(r), "conf": "confirmed"} for r in rows]}]}


def cells(entry):
    return [r["cells"] for r in entry["blocks"][0]["rows"]]


def fill_ctx(*items):
    return {"extract": {"history": [META, *items]}, "catalog": CATALOG}


def files_item(path, **kw):
    return {"kind": "file", "path": path, "authors": {}, "blame": {}, "owner_lines": {}, **kw}


class TestFillConcentration:
    COLUMNS = ["Area", "Owner", "Share", "Status"]

    def test_share_comes_from_owned_lines_and_replaces_what_claude_wrote(self):
        ctx = fill_ctx(person("a@x", "Ann"), person("b@x", "Bob"),
                       files_item("src/core/a.py", blame={"b@x": 100}, owner_lines={"a@x": 75, "b@x": 25}))
        entry = table_entry(self.COLUMNS, ("Core", "Ann", "99%", "shared"))

        assert cells(measured_people.fill(entry, "contributors.concentration", ctx)) == [["Core", "Ann", "75%", "shared"]]

    def test_one_human_owns_everything(self):
        ctx = fill_ctx(person("a@x", "Ann"), files_item("src/core/a.py", blame={"bot": 10}, owner_lines={"a@x": 10}))
        entry = table_entry(self.COLUMNS, ("Core", "Ann", "-", "single owner"))

        assert cells(measured_people.fill(entry, "contributors.concentration", ctx))[0][2] == "100%"

    def test_an_unknown_owner_gets_a_dash(self):
        ctx = fill_ctx(person("a@x", "Ann"), files_item("src/core/a.py", owner_lines={"a@x": 10}))
        entry = table_entry(self.COLUMNS, ("Core", "unknown", "40%", "shared"))

        assert cells(measured_people.fill(entry, "contributors.concentration", ctx))[0][2] == "-"

    def test_a_component_with_no_owned_lines_gets_a_dash(self):
        ctx = fill_ctx(person("a@x", "Ann"))
        entry = table_entry(self.COLUMNS, ("Web", "Ann", "10%", "shared"))

        assert cells(measured_people.fill(entry, "contributors.concentration", ctx))[0][2] == "-"

    def test_without_history_the_entry_is_returned_as_written(self):
        entry = table_entry(self.COLUMNS, ("Core", "Ann", "10%", "shared"))

        assert measured_people.fill(entry, "contributors.concentration", {"extract": {}}) is entry


class TestFillAgents:
    COLUMNS = ["Identity", "Kind", "Areas touched", "Share of commits"]

    def ctx(self):
        return fill_ctx(person("a@x", "Ann", commits=2), person("c@x", "Claude", "agent", commits=6, aliases=["c2@x"]),
                        {"kind": "assistant", "name": "Copilot", "commits": 2, "files": {"src/web/w.py": 2, "src/core/k.py": 1}},
                        files_item("src/core/a.py", authors={"c@x": 4, "a@x": 1}), files_item("src/web/b.py", authors={"c2@x": 2}))

    def test_an_agent_row_gets_its_areas_by_commits_and_its_share(self):
        entry = table_entry(self.COLUMNS, ("Claude", "agent", "-", "-"))

        assert cells(measured_people.fill(entry, "contributors.agents", self.ctx())) == [["Claude", "agent", "Core, Web", "75% (6 commits)"]]

    def test_an_assistant_row_is_filled_from_its_item(self):
        entry = table_entry(self.COLUMNS, ("Copilot", "assistant", "-", "-"))

        assert cells(measured_people.fill(entry, "contributors.agents", self.ctx())) == [["Copilot", "assistant", "Web, Core", "25% (2 commits)"]]

    def test_an_identity_that_matches_nothing_gets_dashes(self):
        entry = table_entry(self.COLUMNS, ("Ghost", "bot", "x", "y"))

        assert cells(measured_people.fill(entry, "contributors.agents", self.ctx())) == [["Ghost", "bot", "-", "-"]]
