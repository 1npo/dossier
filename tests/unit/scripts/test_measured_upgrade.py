import re

import measured
import measured_upgrade

SNAP = {"as_of": "2026-11-05", "source": "x", "products": {
    "python": [{"cycle": "3.14", "eol": "2030-10-31", "latest": "3.14.10"}, {"cycle": "3.10", "eol": "2026-10-31", "latest": "3.10.20"},
               {"cycle": "3.9", "eol": None, "latest": "3.9.1"}],
    "django": [{"cycle": "5.2", "eol": "2028-04-30", "latest": "5.2.9"}, {"cycle": "3.2", "eol": "2024-04-01", "latest": "3.2.25"}]}}


class Refs:
    def mark(self, cites):
        return f"[{','.join(cites)}]"


def ctx(requires=None, pyver=None, deps=(), commit_date="2026-06-01"):
    manifests = [{"path": "pyproject.toml", "extra": {"requires-python": requires} if requires else {}, "dependencies": [{"name": d["n"]} for d in deps]}]
    return {"facts": {"repo": {"commit_date": commit_date}, "manifests": manifests, "dependencies": {"deps": list(deps)}},
            "read": lambda p: pyver if p == ".python-version" else None, "extract": {}}


class TestRows:
    def test_python_pinned_by_version_file_wins_over_requires_python(self):
        got = measured_upgrade.rows(ctx(requires=">=3.10", pyver="3.14\n"), SNAP)

        assert got == [("Python", "3.14", "3.14.10 (latest)", "supported until 2030-10-31", ".python-version")]

    def test_requires_python_lower_bound_names_the_cycle(self):
        got = measured_upgrade.rows(ctx(requires=">=3.10"), SNAP)

        assert got[0][1:] == ("requires-python >=3.10", "3.14.10 (latest)", "supported until 2026-10-31", "pyproject.toml")

    def test_past_end_of_life_is_stated_with_the_date(self):
        got = measured_upgrade.rows(ctx(requires=">=3.10", commit_date="2027-01-01"), SNAP)

        assert got[0][3] == "end of life since 2026-10-31"

    def test_cycle_missing_from_the_data_says_so(self):
        assert measured_upgrade.rows(ctx(requires=">=2.7"), SNAP)[0][3] == "not in the data"
        assert measured_upgrade.rows(ctx(requires=">=3.9"), SNAP)[0][3] == "not in the data"

    def test_known_package_is_listed_with_its_cycle(self):
        deps = [{"n": "Django", "v": "3.2.1"}, {"n": "flask", "v": "3.0.0"}]

        got = measured_upgrade.rows(ctx(deps=deps), SNAP)

        assert got == [("Django", "3.2.1", "5.2.9 (latest)", "end of life since 2024-04-01", "pyproject.toml")]

    def test_nothing_known_gives_no_rows(self):
        assert measured_upgrade.rows(ctx(), SNAP) == []


class TestCard:
    def test_caption_names_the_snapshot_date_and_table_has_a_row_per_item(self):
        html = measured.body("change.upgrade-burden", ctx(requires=">=3.10"), Refs())

        assert re.search(r"Data as of \d{4}-\d{2}-\d{2}, from endoflife.date\.", html)
        assert 'id="t-change-upgrade-burden"' in html

    def test_no_rows_says_none_found(self):
        assert "none-found" in measured.body("change.upgrade-burden", ctx(), Refs())


class TestShippedSnapshot:
    def test_has_the_five_products(self):
        snap = measured_upgrade.load_snapshot()

        assert sorted(snap["products"]) == ["django", "dotnet", "nodejs", "postgresql", "python"] and re.fullmatch(r"\d{4}-\d{2}-\d{2}", snap["as_of"])
