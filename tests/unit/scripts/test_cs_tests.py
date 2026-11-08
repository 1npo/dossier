import cs_tests


def attr(name, args=""):
    return {"name": name, "args": args, "line": 1}


def method(name, *attrs):
    return {"name": name, "kind": "method", "modifiers": ["public"], "line": 5, "end_line": 5, "attributes": list(attrs), "type": "void", "static": False, "params": []}


def field(name, mods, type_="int", init=""):
    return {"name": name, "kind": "field", "modifiers": list(mods), "line": 4, "end_line": 4, "attributes": [], "type": type_, "static": "static" in mods, "params": [], "init": init}


def typ(name, members=(), attrs=(), bases=()):
    return {"name": name, "kind": "class", "modifiers": ["public"], "line": 3, "end_line": 30, "attributes": list(attrs), "bases": list(bases), "partial": False,
            "outer": None, "namespace": "N", "params": [], "members": list(members)}


def decl(*types):
    return {"types": list(types)}


def proj(name="T", packages=(), files=("T/a.cs",), test=True):
    return {"path": f"{name}/{name}.csproj", "name": name, "packages": list(packages), "files": list(files), "test": test}


def run(types, project=None, text=""):
    project = project or proj(packages=["xunit"])
    got = cs_tests.tests({"T/a.cs": decl(*types)}, {"projects": [project]}, lambda p: text, {"T/a.cs"})
    return got[0]


class TestCounts:
    def test_xunit_forms_are_counted_once_per_method_with_skips_inside_the_tests(self):
        item = run([typ("A", [method("a", attr("Fact")), method("b", attr("Theory"), attr("InlineData", "1")), method("c", attr("Fact", 'Skip = "flaky"'))])])

        assert (item["tests"], item["skips"], item["classes"], item["xfails"]) == (3, 1, 1, 0)

    def test_nunit_forms_ignore_and_explicit_count_as_skips(self):
        item = run([typ("A", [method("a", attr("Test")), method("b", attr("TestCase", "1")), method("c", attr("TestCaseSource", '"x"')), method("d", attr("Test"), attr("Ignore", '"x"')),
                              method("e", attr("Test"), attr("Explicit"))], [attr("TestFixture")])], proj(packages=["NUnit"]))

        assert (item["tests"], item["skips"], item["classes"], item["framework"]) == (5, 2, 1, "nunit")

    def test_mstest_forms(self):
        item = run([typ("A", [method("a", attr("TestMethod")), method("b", attr("DataTestMethod"))], [attr("TestClass")])], proj(packages=["MSTest.TestFramework"]))

        assert (item["tests"], item["classes"], item["framework"]) == (2, 1, "mstest")

    def test_a_helper_class_has_no_tests_and_no_class_count(self):
        item = run([typ("TestHelpers", [method("NewOrder")])])

        assert (item["tests"], item["classes"], item["mocks"], item["fixtures"]) == (0, 0, 0, 0)

    def test_fixtures_come_from_base_lists_and_setup_attributes(self):
        item = run([typ("A", [method("Init", attr("SetUp")), method("Boot", attr("OneTimeSetUp"))], bases=["IClassFixture<WebApplicationFactory<Program>>"])])

        assert item["fixtures"] == 3

    def test_mocks_are_counted_in_the_text(self):
        item = run([typ("A")], text="new Mock<IClock>(); Substitute.For<IX>(); A.Fake<IY>(); Mock.Of<IZ>(); var mock = 1;")

        assert item["mocks"] == 4

    def test_the_item_has_the_python_shape(self):
        item = run([typ("A")])

        assert set(item) == {"kind", "path", "test_kind", "framework", "tests", "classes", "skips", "xfails", "mocks", "fixtures", "imports", "paths"}


class TestKindAndFramework:
    def test_framework_from_packages(self):
        assert [cs_tests.framework(p) for p in (["xunit.v3"], ["NUnit"], ["MSTest.Sdk"], ["TUnit"], ["Moq"])] == ["xunit", "nunit", "mstest", "tunit", "unknown"]

    def test_integration_from_a_package_or_a_name(self):
        assert cs_tests.test_kind(proj(packages=["Microsoft.AspNetCore.Mvc.Testing"])) == "integration"
        assert cs_tests.test_kind(proj("Shop.Functional.Tests")) == "integration"
        assert cs_tests.test_kind(proj(packages=["Testcontainers.PostgreSql"])) == "integration"

    def test_e2e_beats_integration(self):
        assert cs_tests.test_kind(proj(packages=["Microsoft.Playwright", "Respawn"])) == "e2e"
        assert cs_tests.test_kind(proj("Shop.AcceptanceTests")) == "e2e"

    def test_plain_projects_and_loose_files_are_unit(self):
        assert cs_tests.test_kind(proj()) == "unit" and cs_tests.test_kind(None) == "unit"


class TestStaticState:
    def state(self, *members):
        return cs_tests.module_state({"a.cs": decl(typ("A", members))})

    def test_a_static_field_that_changes_is_state_and_a_property_or_instance_field_is_not(self):
        got = self.state(field("_count", ["static"]), field("_x", ["private"]), {**field("Name", ["public"]), "kind": "property", "static": True})

        assert [g["name"] for g in got] == ["_count"]
        assert (got[0]["rule"], got[0]["category"], got[0]["snippet"]) == ("dossier.csharp.state.static-mutable", "global-state", "static int _count")

    def test_readonly_and_const_are_not_state_unless_a_collection(self):
        got = self.state(field("Name", ["static", "readonly"], "string", '"x"'), field("K", ["const"], "int", "1"),
                         field("_cache", ["private", "static", "readonly"], "Dictionary<string,int>", "new()"),
                         field("_list", ["static", "readonly"], "List<int>", "new List<int>()"), field("_empty", ["static", "readonly"], "int[]", "[]"))

        assert [g["name"] for g in got] == ["_cache", "_list", "_empty"]

    def test_target_typed_new_counts_only_for_a_collection_type(self):
        got = self.state(field("_cache", ["static", "readonly"], "Dictionary<string,int>", "new()"), field("_clock", ["static", "readonly"], "Clock", "new()"))

        assert [g["name"] for g in got] == ["_cache"]

    def test_skipped_files_give_nothing(self):
        assert cs_tests.module_state({"a.cs": decl(typ("A", [field("_c", ["static"])]))}, skip={"a.cs"}) == []


class TestConfigs:
    def cfgs(self, files, test=True):
        projects = {"projects": [{"path": "T/T.csproj", "name": "T", "test": test}]}
        return cs_tests.test_configs(sorted(files), files.get, projects)

    def test_runsettings_and_xunit_json(self):
        got = self.cfgs({"T/x.runsettings": "<RunSettings/>", "T/xunit.runner.json": "{}", "T/other.json": "{}"})

        assert [(c["path"], c["tool"]) for c in got] == [("T/x.runsettings", "runsettings"), ("T/xunit.runner.json", "xunit")]

    def test_coverlet_runsettings_reads_its_threshold(self):
        got = self.cfgs({"coverlet.runsettings": "<Threshold>80</Threshold>"})

        assert got == [{"kind": "config", "path": "coverlet.runsettings", "tool": "coverlet", "settings": {"coverage_threshold": 80}}]

    def test_a_threshold_in_a_test_project_file_is_coverage(self):
        got = self.cfgs({"T/T.csproj": "<Project><PropertyGroup><Threshold>70,85</Threshold></PropertyGroup></Project>"})

        assert [(c["tool"], c["settings"]) for c in got] == [("coverlet", {"coverage_threshold": 70})]

    def test_a_threshold_in_a_non_test_project_is_ignored(self):
        assert self.cfgs({"T/T.csproj": "<Threshold>70</Threshold>"}, test=False) == []
