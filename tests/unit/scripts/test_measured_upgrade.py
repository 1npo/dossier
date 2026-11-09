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


SNAP_JS = {**SNAP, "products": {**SNAP["products"],
    "nodejs": [{"cycle": "26", "eol": "2029-04-30", "latest": "26.13.0"}, {"cycle": "22", "eol": "2027-04-30", "latest": "22.22.0"},
               {"cycle": "18", "eol": "2025-04-30", "latest": "18.20.8"}],
    "react": [{"cycle": "19", "eol": None, "latest": "19.3.1"}, {"cycle": "18", "eol": None, "latest": "18.3.1"}],
    "nextjs": [{"cycle": "16", "eol": None, "latest": "16.4.5"}, {"cycle": "14", "eol": "2025-10-26", "latest": "14.2.35"}]}}


def jsctx(files=None, deps=(), commit_date="2026-06-01"):
    files = files or {}
    return {"facts": {"repo": {"commit_date": commit_date}, "manifests": [], "dependencies": {"deps": list(deps)}},
            "tree": set(files), "read": files.get, "extract": {}}


class TestNodeRow:
    def test_nvmrc_names_the_runtime(self):
        got = measured_upgrade.rows(jsctx({".nvmrc": "v22.1.0\n"}), SNAP_JS)

        assert got == [("Node.js", "v22.1.0", "26.13.0 (latest)", "supported until 2027-04-30", ".nvmrc")]

    def test_node_version_file_comes_after_nvmrc_and_before_engines(self):
        files = {".node-version": "18\n", "package.json": '{"engines": {"node": ">=22"}}'}

        assert measured_upgrade.rows(jsctx(files), SNAP_JS)[0][1:] == ("18", "26.13.0 (latest)", "end of life since 2025-04-30", ".node-version")

    def test_engines_of_the_first_package_is_the_last_resort(self):
        files = {"package.json": '{"engines": {"node": ">=22"}}', "apps/a/package.json": '{"engines": {"node": ">=18"}}'}

        assert measured_upgrade.rows(jsctx(files), SNAP_JS)[0] == ("Node.js", "engines.node >=22", "26.13.0 (latest)", "supported until 2027-04-30", "package.json")

    def test_a_pin_with_no_number_is_skipped(self):
        assert measured_upgrade.rows(jsctx({".nvmrc": "lts/iron\n"}), SNAP_JS) == []

    def test_a_repository_with_no_node_pin_has_no_node_row(self):
        assert measured_upgrade.rows(jsctx({"package.json": "{}"}), SNAP_JS) == []

    def test_python_comes_before_node(self):
        got = measured_upgrade.rows({**ctx(requires=">=3.10"), "tree": {".nvmrc"}, "read": lambda p: "22" if p == ".nvmrc" else None}, SNAP_JS)

        assert [r[0] for r in got] == ["Python", "Node.js"]


class TestFrameworkRows:
    def test_react_and_next_are_matched_by_major_version(self):
        deps = [{"n": "react", "v": "^18.2.0"}, {"n": "next", "v": "14.2.0"}]

        got = measured_upgrade.rows(jsctx(deps=deps), SNAP_JS)

        assert [(r[0], r[2], r[3]) for r in got] == [("next", "16.4.5 (latest)", "end of life since 2025-10-26"), ("react", "19.3.1 (latest)", "not in the data")]

    def test_a_dependency_that_is_not_a_version_is_skipped(self):
        assert measured_upgrade.rows(jsctx(deps=[{"n": "react", "v": "workspace:*"}]), SNAP_JS) == []

    def test_the_same_version_in_two_packages_is_one_row(self):
        deps = [{"n": "react", "v": "18.2.0"}, {"n": "react", "v": "18.2.0"}]

        assert len(measured_upgrade.rows(jsctx(deps=deps), SNAP_JS)) == 1

    def test_django_still_uses_major_and_minor(self):
        got = measured_upgrade.rows(ctx(deps=[{"n": "Django", "v": "3.2.1"}]), SNAP_JS)

        assert got[0][2:4] == ("5.2.9 (latest)", "end of life since 2024-04-01")


class TestShippedSnapshot:
    def test_it_knows_the_javascript_products_and_keeps_the_python_ones(self):
        snap = measured_upgrade.load_snapshot()

        assert {"python", "django", "nodejs", "react", "nextjs"} <= set(snap["products"])


DOTNET_SNAP = {"as_of": "2026-11-05", "source": "x", "products": {
    "dotnet": [{"cycle": "10", "eol": "2028-11-14", "latest": "10.0.13"}, {"cycle": "9", "eol": "2026-11-10", "latest": "9.0.21"},
               {"cycle": "8", "eol": "2026-11-10", "latest": "8.0.32"}]}}


def csctx(*projects, commit_date="2026-06-01"):
    graph = [{"kind": "cs-project", "path": path, "name": path, "frameworks": list(frameworks), "test": test}
             for path, frameworks, test in projects]
    return {"facts": {"repo": {"commit_date": commit_date}, "manifests": []}, "read": lambda p: None, "extract": {"graph": graph}}


class TestDotnetRows:
    def test_a_supported_framework_gives_a_row_with_its_end_date(self):
        got = measured_upgrade.rows(csctx(("src/A/A.csproj", ["net10.0"], False)), DOTNET_SNAP)

        assert got == [(".NET", "TargetFramework net10.0", "10.0.13 (latest)", "supported until 2028-11-14", "src/A/A.csproj")]

    def test_a_framework_past_its_end_of_life_says_since_when_at_a_later_commit_date(self):
        got = measured_upgrade.rows(csctx(("src/A/A.csproj", ["net8.0"], False), commit_date="2026-12-01"), DOTNET_SNAP)

        assert got[0][3] == "end of life since 2026-11-10"

    def test_a_platform_suffix_is_ignored_for_the_cycle(self):
        got = measured_upgrade.rows(csctx(("src/A/A.csproj", ["net8.0-windows"], False)), DOTNET_SNAP)

        assert got[0][1] == "TargetFramework net8.0-windows" and got[0][3] == "supported until 2026-11-10"

    def test_standard_and_old_frameworks_give_no_row(self):
        projects = [("a/A.csproj", ["netstandard2.0"], False), ("b/B.csproj", ["net48"], False), ("c/C.csproj", ["netcoreapp2.1"], False)]

        assert measured_upgrade.rows(csctx(*projects), DOTNET_SNAP) == []

    def test_test_projects_give_no_row(self):
        assert measured_upgrade.rows(csctx(("t/T.csproj", ["net10.0"], True)), DOTNET_SNAP) == []

    def test_one_row_per_distinct_framework_naming_the_first_project(self):
        projects = [("b/B.csproj", ["net10.0", "net8.0"], False), ("a/A.csproj", ["net10.0"], False)]

        got = measured_upgrade.rows(csctx(*projects), DOTNET_SNAP)

        assert [(r[1], r[4]) for r in got] == [("TargetFramework net10.0", "a/A.csproj"), ("TargetFramework net8.0", "b/B.csproj")]

    def test_the_dotnet_rows_follow_the_python_and_node_rows(self):
        c = ctx(requires=">=3.10")
        c["extract"] = csctx(("src/A/A.csproj", ["net10.0"], False))["extract"]

        got = measured_upgrade.rows(c, {**SNAP, "products": {**SNAP["products"], **DOTNET_SNAP["products"]}})

        assert [r[0] for r in got] == ["Python", ".NET"]

    def test_a_python_context_gives_the_rows_it_gave(self):
        assert [r[0] for r in measured_upgrade.rows(ctx(requires=">=3.10"), SNAP)] == ["Python"]
