import cs_project


def csproj(sdk="Microsoft.NET.Sdk", props="", items=""):
    return f'<Project Sdk="{sdk}"><PropertyGroup>{props}</PropertyGroup><ItemGroup>{items}</ItemGroup></Project>'


def find(files):
    return cs_project.projects(sorted(files), lambda p: files.get(p))


def by_name(result):
    return {p["name"]: p for p in result["projects"]}


CONDUIT = {
    "Conduit.slnx": '<Solution><Project Path="build/build.csproj" /><Project Path="src/Conduit/Conduit.csproj" />'
                    '<Project Path="tests/Conduit.IntegrationTests/Conduit.IntegrationTests.csproj" /></Solution>',
    "Directory.Build.props": "<Project><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>",
    "build/build.csproj": csproj(props="<OutputType>Exe</OutputType>", items='<PackageReference Include="Bullseye" />'),
    "build/Program.cs": "class P {}",
    "src/Conduit/Conduit.csproj": csproj("Microsoft.NET.Sdk.Web", items='<PackageReference Include="Serilog" />'),
    "src/Conduit/Program.cs": "class P {}",
    "src/Conduit/packages.lock.json": "{}",
    "tests/Conduit.IntegrationTests/Conduit.IntegrationTests.csproj": csproj(
        items='<ProjectReference Include="..\\..\\src\\Conduit\\Conduit.csproj" /><PackageReference Include="xunit" />'),
    "tests/Conduit.IntegrationTests/T.cs": "class T {}",
}


class TestProjectsConduitShape:
    def test_solution_lists_its_three_projects(self):
        got = find(CONDUIT)

        assert got["solutions"] == [{"path": "Conduit.slnx", "projects": [
            "build/build.csproj", "src/Conduit/Conduit.csproj", "tests/Conduit.IntegrationTests/Conduit.IntegrationTests.csproj"]}]

    def test_web_sdk_is_an_exe_and_not_packable(self):
        p = by_name(find(CONDUIT))["Conduit"]

        assert (p["output_type"], p["packable"], p["test"], p["lock"]) == ("Exe", False, False, True)

    def test_target_framework_comes_from_directory_build_props(self):
        assert by_name(find(CONDUIT))["Conduit"]["frameworks"] == ["net10.0"]

    def test_test_project_references_the_app_with_backslashes_resolved(self):
        p = by_name(find(CONDUIT))["Conduit.IntegrationTests"]

        assert p["test"] is True and p["references"] == ["src/Conduit/Conduit.csproj"]

    def test_files_belong_to_their_project(self):
        got = by_name(find(CONDUIT))

        assert got["Conduit"]["files"] == ["src/Conduit/Program.cs"]
        assert got["build"]["lock"] is False

    def test_targets_are_the_solution_only(self):
        assert find(CONDUIT)["targets"] == ["Conduit.slnx"]

    def test_source_roots_are_src_and_tests_with_none_for_build(self):
        result = find(CONDUIT)

        roots = cs_project.source_roots(result, list(CONDUIT))

        assert sorted((r["path"].split("/")[0], r["root"]) for r in roots) == [("src", "src"), ("tests", "tests")]


class TestProperties:
    def test_conditioned_group_is_ignored(self):
        files = {"Directory.Build.props": '<Project><PropertyGroup Condition="\'$(X)\'==\'1\'"><IsPackable>false</IsPackable></PropertyGroup></Project>',
                 "a/a.csproj": csproj(props="<TargetFramework>net8.0</TargetFramework>"), "a/A.cs": ""}

        assert by_name(find(files))["a"]["packable"] is True

    def test_project_wins_over_the_props_file(self):
        files = {"Directory.Build.props": "<Project><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>",
                 "a/a.csproj": csproj(props="<TargetFramework>net9.0</TargetFramework>")}

        assert by_name(find(files))["a"]["frameworks"] == ["net9.0"]

    def test_nearest_props_file_wins(self):
        files = {"Directory.Build.props": "<Project><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>",
                 "x/Directory.Build.props": "<Project><PropertyGroup><TargetFramework>net9.0</TargetFramework></PropertyGroup></Project>",
                 "x/a/a.csproj": csproj()}

        assert by_name(find(files))["a"]["frameworks"] == ["net9.0"]

    def test_old_style_namespace_on_the_project_element_is_read(self):
        text = ('<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003"><PropertyGroup>'
                '<OutputType>Exe</OutputType></PropertyGroup></Project>')

        assert by_name(find({"a/a.csproj": text}))["a"]["output_type"] == "Exe"

    def test_bom_is_stripped(self):
        assert by_name(find({"a/a.csproj": "﻿" + csproj(props="<OutputType>Exe</OutputType>")}))["a"]["output_type"] == "Exe"

    def test_bad_xml_is_listed_with_an_error(self):
        got = by_name(find({"a/a.csproj": "<Project><Property", "a/A.cs": ""}))["a"]

        assert got["error"] and got["files"] == ["a/A.cs"]


class TestLibraryShape:
    FILES = {
        "Lib.sln": 'Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = "Lib", "src\\Lib\\Lib.csproj", "{1}"\nEndProject\n'
                   'Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = "Lib.Tests", "test\\Lib.Tests\\Lib.Tests.csproj", "{2}"\nEndProject\n',
        "src/Lib/Lib.csproj": csproj(props="<TargetFrameworks>netstandard2.0;net8.0;net10.0</TargetFrameworks><PackageId>My.Lib</PackageId>"),
        "src/Lib/X.cs": "",
        "test/Lib.Tests/Lib.Tests.csproj": csproj(props="<IsTestProject>true</IsTestProject>"),
    }

    def test_classic_solution_is_read(self):
        assert [p for p in find(self.FILES)["solutions"][0]["projects"]] == ["src/Lib/Lib.csproj", "test/Lib.Tests/Lib.Tests.csproj"]

    def test_several_frameworks_and_packable(self):
        p = by_name(find(self.FILES))["Lib"]

        assert p["frameworks"] == ["netstandard2.0", "net8.0", "net10.0"] and p["packable"] is True and p["package_id"] == "My.Lib"

    def test_is_test_project_property_marks_a_test_project(self):
        p = by_name(find(self.FILES))["Lib.Tests"]

        assert p["test"] is True and p["packable"] is False


class TestProjectKinds:
    def test_is_packable_false_is_respected(self):
        assert by_name(find({"a/a.csproj": csproj(props="<IsPackable>false</IsPackable>")}))["a"]["packable"] is False

    def test_pack_as_tool_exe_is_packable(self):
        p = by_name(find({"a/a.csproj": csproj(props="<OutputType>Exe</OutputType><PackAsTool>true</PackAsTool>")}))["a"]

        assert p["packable"] is True

    def test_exe_is_not_packable(self):
        assert by_name(find({"a/a.csproj": csproj(props="<OutputType>Exe</OutputType>")}))["a"]["packable"] is False

    def test_worker_sdk_is_an_exe_and_not_packable(self):
        p = by_name(find({"a/a.csproj": csproj("Microsoft.NET.Sdk.Worker")}))["a"]

        assert (p["output_type"], p["packable"]) == ("Exe", False)

    def test_mstest_sdk_marks_a_test_project(self):
        assert by_name(find({"a/a.csproj": csproj("MSTest.Sdk/3.6.0")}))["a"]["test"] is True

    def test_test_package_marks_a_test_project(self):
        for package in ("Microsoft.NET.Test.Sdk", "xunit.v3", "NUnit", "MSTest.TestFramework", "TUnit"):
            p = by_name(find({"a/a.csproj": csproj(items=f'<PackageReference Include="{package}" />')}))["a"]

            assert p["test"] is True

    def test_internals_visible_to_items_are_friends(self):
        p = by_name(find({"a/a.csproj": csproj(items='<InternalsVisibleTo Include="A.Tests" />')}))["a"]

        assert p["friends"] == ["A.Tests"]

    def test_fsproj_is_listed_with_its_language_and_no_files(self):
        files = {"f/f.fsproj": csproj(), "f/F.cs": ""}

        p = by_name(find(files))["f"]

        assert p["language"] == "F#" and p["files"] == []


class TestFilesAndTargets:
    def test_nested_project_takes_the_nearest_files(self):
        files = {"a/a.csproj": csproj(), "a/A.cs": "", "a/b/b.csproj": csproj(), "a/b/B.cs": ""}

        got = by_name(find(files))

        assert got["a"]["files"] == ["a/A.cs"] and got["b"]["files"] == ["a/b/B.cs"]

    def test_cs_file_under_no_project_is_loose(self):
        assert find({"x/X.cs": ""})["loose_files"] == ["x/X.cs"]

    def test_loose_project_outside_any_solution_is_a_target(self):
        files = {**CONDUIT, "tools/Legacy/Legacy.csproj": csproj(props="<OutputType>Exe</OutputType>")}

        assert find(files)["targets"] == ["Conduit.slnx", "tools/Legacy/Legacy.csproj"]

    def test_slnx_in_a_subfolder_resolves_paths_against_it(self):
        files = {"samples/S.slnx": '<Solution><Project Path="S/S.csproj" /></Solution>', "samples/S/S.csproj": csproj()}

        assert find(files)["solutions"][0]["projects"] == ["samples/S/S.csproj"]

    def test_single_project_gets_its_own_folder_as_root(self):
        result = find({"src/App/App.csproj": csproj()})

        assert [r["root"] for r in cs_project.source_roots(result, [])] == ["src/App"]

    def test_project_at_the_repository_root_has_no_source_root(self):
        assert cs_project.source_roots(find({"App.csproj": csproj(), "a/a.csproj": csproj()}), []) == []


class TestFrameworksNamed:
    def test_known_framework_packages_are_named_sorted(self):
        files = {"a/a.csproj": csproj(items='<PackageReference Include="Carter" /><PackageReference Include="FastEndpoints" />'
                                              '<PackageReference Include="MediatR" />')}

        assert cs_project.frameworks_named(find(files)) == ["Carter", "FastEndpoints"]


class TestIsGenerated:
    def read(self, text):
        return lambda p: text

    def test_designer_file_in_any_case(self):
        assert cs_project.is_generated("M/Init.Designer.cs", self.read("")) and cs_project.is_generated("M/Init.designer.CS", self.read(""))

    def test_g_cs_and_g_i_cs_in_any_case(self):
        assert cs_project.is_generated("a.g.cs", self.read("")) and cs_project.is_generated("X.G.CS", self.read("")) \
            and cs_project.is_generated("a.g.i.cs", self.read(""))

    def test_auto_generated_header_in_the_first_ten_lines(self):
        assert cs_project.is_generated("a.cs", self.read("// <auto-generated />\nclass A {}"))

    def test_header_after_line_ten_does_not_count(self):
        assert not cs_project.is_generated("a.cs", self.read("\n" * 10 + "// <auto-generated />"))

    def test_plain_source_is_not_generated(self):
        assert not cs_project.is_generated("a.cs", self.read("class A {}"))


class TestSdkNames:
    def test_aspire_sdk_attribute_names_the_framework_without_a_package(self):
        files = {"host/Host.csproj": csproj(sdk="Aspire.AppHost.Sdk/13.6.4")}
        result = find(files)

        assert cs_project.frameworks_named(result) == ["Aspire.Hosting.AppHost"]
        assert by_name(result)["Host"]["sdks"] == ["Aspire.AppHost.Sdk"]

    def test_sdk_element_names_the_framework(self):
        text = '<Project Sdk="Microsoft.NET.Sdk"><Sdk Name="Aspire.AppHost.Sdk" Version="13.0.0" /></Project>'
        result = find({"host/Host.csproj": text})

        assert cs_project.frameworks_named(result) == ["Aspire.Hosting.AppHost"]
        assert by_name(result)["Host"]["sdks"] == ["Microsoft.NET.Sdk", "Aspire.AppHost.Sdk"]

    def test_several_names_in_one_attribute(self):
        result = find({"a/a.csproj": csproj(sdk="Aspire.AppHost.Sdk;Other.Sdk/1.0")})

        assert by_name(result)["a"]["sdks"] == ["Aspire.AppHost.Sdk", "Other.Sdk"]

    def test_sdk_field_is_still_the_first_name(self):
        assert by_name(find({"a/a.csproj": csproj(sdk="Aspire.AppHost.Sdk/1.0;B")}))["a"]["sdk"] == "Aspire.AppHost.Sdk"

    def test_package_and_sdk_report_the_framework_once(self):
        files = {"a/a.csproj": csproj(sdk="Aspire.AppHost.Sdk/13", items='<PackageReference Include="Aspire.Hosting.AppHost" />')}

        assert cs_project.frameworks_named(find(files)) == ["Aspire.Hosting.AppHost"]
