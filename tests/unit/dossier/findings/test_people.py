from dossier.findings import people
from people_items import CATALOG, file_item, humans, person


class TestComponentStats:
    def ctx(self, *files):
        return {"extract": {"history": list(files)}, "catalog": CATALOG}

    def test_files_add_up_per_component(self):
        ctx = self.ctx(file_item("src/core/a.py", {"x": 2}, {"x": 5}, {"y": 5}), file_item("src/core/b.py", {"x": 1, "y": 3}, {"y": 4}, {"y": 4}))

        stats = people.component_stats(ctx)["Core"]

        assert stats["files"] == 2 and stats["commits"] == {"x": 3, "y": 3}
        assert stats["lines"] == {"x": 5, "y": 4} and stats["owned"] == {"y": 9} and stats["approx"] is False

    def test_a_file_without_blame_marks_the_component_approximate(self):
        stats = people.component_stats(self.ctx(file_item("src/web/a.py", {"x": 2})))["Web"]

        assert stats["approx"] is True and stats["commits"] == {"x": 2} and stats["owned"] == {}

    def test_a_file_in_no_component_is_left_out(self):
        stats = people.component_stats(self.ctx(file_item("docs/a.py", {"x": 2})))

        assert stats["Core"]["files"] == 0 and stats["Web"]["files"] == 0

    def test_no_catalog_gives_nothing(self):
        assert people.component_stats({"extract": {"history": []}}) == {}


class TestNamesOf:
    def test_aliases_map_to_the_merged_name(self):
        ctx = {"extract": {"history": [{"kind": "person", "person": "a@x", "name": "Ann", "aliases": ["a@y"]}]}}

        assert people.names_of(ctx) == {"a@x": "Ann", "a@y": "Ann"}


class TestBusFactor:
    def test_one_human_is_a_bus_factor_of_one(self):
        assert people.bus_factor(humans(100)) == {"bus_factor": 1, "top_owner_share": 100}

    def test_two_humans_with_a_big_share_still_need_one(self):
        assert people.bus_factor(humans(60, 40)) == {"bus_factor": 1, "top_owner_share": 60}

    def test_an_even_split_needs_two(self):
        assert people.bus_factor(humans(50, 50)) == {"bus_factor": 2, "top_owner_share": 50}

    def test_three_humans_need_two_when_the_first_has_less_than_half(self):
        assert people.bus_factor(humans(40, 35, 25)) == {"bus_factor": 2, "top_owner_share": 40}

    def test_agents_and_bots_are_left_out(self):
        ctx = humans(10)
        ctx["extract"]["history"] += [person("a", "Claude", "agent", owned_lines=900), person("b", "bot", "bot", owned_lines=900)]

        assert people.bus_factor(ctx) == {"bus_factor": 1, "top_owner_share": 100}

    def test_no_human_lines_gives_none(self):
        assert people.bus_factor(humans(0)) == {"bus_factor": None, "top_owner_share": None}
