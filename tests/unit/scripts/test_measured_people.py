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
