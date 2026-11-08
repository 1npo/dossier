import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import measured_people  # noqa: E402


def file_item(path, authors=None, blame=None, owner_lines=None):
    return {"kind": "file", "path": path, "authors": authors or {}, "blame": blame, "owner_lines": owner_lines}


CATALOG = [{"name": "Core", "paths": ["src/core/"]}, {"name": "Web", "paths": ["src/web/"]}]


class TestComponentStats:
    def ctx(self, *files):
        return {"extract": {"history": list(files)}, "catalog": CATALOG}

    def test_files_add_up_per_component(self):
        ctx = self.ctx(file_item("src/core/a.py", {"x": 2}, {"x": 5}, {"y": 5}), file_item("src/core/b.py", {"x": 1, "y": 3}, {"y": 4}, {"y": 4}))

        stats = measured_people.component_stats(ctx)["Core"]

        assert stats["files"] == 2 and stats["commits"] == {"x": 3, "y": 3}
        assert stats["lines"] == {"x": 5, "y": 4} and stats["owned"] == {"y": 9} and stats["approx"] is False

    def test_a_file_without_blame_marks_the_component_approximate(self):
        stats = measured_people.component_stats(self.ctx(file_item("src/web/a.py", {"x": 2})))["Web"]

        assert stats["approx"] is True and stats["commits"] == {"x": 2} and stats["owned"] == {}

    def test_a_file_in_no_component_is_left_out(self):
        stats = measured_people.component_stats(self.ctx(file_item("docs/a.py", {"x": 2})))

        assert stats["Core"]["files"] == 0 and stats["Web"]["files"] == 0

    def test_no_catalog_gives_nothing(self):
        assert measured_people.component_stats({"extract": {"history": []}}) == {}


class TestNamesOf:
    def test_aliases_map_to_the_merged_name(self):
        ctx = {"extract": {"history": [{"kind": "person", "person": "a@x", "name": "Ann", "aliases": ["a@y"]}]}}

        assert measured_people.names_of(ctx) == {"a@x": "Ann", "a@y": "Ann"}


def person(ident, name, kind="human", commits=1, owned_lines=0, aliases=()):
    return {"kind": "person", "person": ident, "name": name, "type": kind, "commits": commits, "owned_lines": owned_lines, "aliases": list(aliases)}


META = {"kind": "meta", "status": "ok"}


def humans(*lines):
    return {"extract": {"history": [META] + [person(f"h{i}", f"H{i}", owned_lines=n) for i, n in enumerate(lines)]}}


class TestBusFactor:
    def test_one_human_is_a_bus_factor_of_one(self):
        assert measured_people.bus_factor(humans(100)) == {"bus_factor": 1, "top_owner_share": 100}

    def test_two_humans_with_a_big_share_still_need_one(self):
        assert measured_people.bus_factor(humans(60, 40)) == {"bus_factor": 1, "top_owner_share": 60}

    def test_an_even_split_needs_two(self):
        assert measured_people.bus_factor(humans(50, 50)) == {"bus_factor": 2, "top_owner_share": 50}

    def test_three_humans_need_two_when_the_first_has_less_than_half(self):
        assert measured_people.bus_factor(humans(40, 35, 25)) == {"bus_factor": 2, "top_owner_share": 40}

    def test_agents_and_bots_are_left_out(self):
        ctx = humans(10)
        ctx["extract"]["history"] += [person("a", "Claude", "agent", owned_lines=900), person("b", "bot", "bot", owned_lines=900)]

        assert measured_people.bus_factor(ctx) == {"bus_factor": 1, "top_owner_share": 100}

    def test_no_human_lines_gives_none(self):
        assert measured_people.bus_factor(humans(0)) == {"bus_factor": None, "top_owner_share": None}


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
