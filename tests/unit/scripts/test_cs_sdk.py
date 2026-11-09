import cs_sdk


class TestParseGlobalJson:
    def test_plain_file_gives_the_sdk_object(self):
        text = '{"sdk": {"version": "10.0.403", "rollForward": "latestFeature"}}'

        assert cs_sdk.parse_global_json(text) == {"version": "10.0.403", "rollForward": "latestFeature"}

    def test_comments_are_tolerated_and_urls_in_strings_survive(self):
        text = '// top\n{ /* c */ "sdk": { "version": "9.0.100" }, "msbuild-sdks": {"A": "http://x/y"} }'

        assert cs_sdk.parse_global_json(text) == {"version": "9.0.100"}

    def test_invalid_json_gives_none(self):
        assert cs_sdk.parse_global_json("{nope") is None

    def test_file_without_sdk_gives_none(self):
        assert cs_sdk.parse_global_json("{}") is None


class TestPick:
    def test_latest_feature_accepts_a_later_patch_and_a_later_band(self):
        want = {"version": "8.0.302", "rollForward": "latestFeature"}

        assert cs_sdk.pick(["8.0.303"], want) == "8.0.303"
        assert cs_sdk.pick(["8.0.402"], want) == "8.0.402"

    def test_latest_feature_refuses_an_earlier_patch(self):
        assert cs_sdk.pick(["8.0.301"], {"version": "8.0.302", "rollForward": "latestFeature"}) is None

    def test_latest_patch_stays_in_the_feature_band(self):
        want = {"version": "8.0.102", "rollForward": "latestPatch"}

        assert cs_sdk.pick(["8.0.199"], want) == "8.0.199"
        assert cs_sdk.pick(["8.0.200"], want) is None

    def test_latest_major_crosses_majors(self):
        assert cs_sdk.pick(["8.0.100"], {"version": "7.0.200", "rollForward": "latestMajor"}) == "8.0.100"

    def test_latest_minor_stays_in_the_major(self):
        want = {"version": "8.0.100", "rollForward": "latestMinor"}

        assert cs_sdk.pick(["8.1.100"], want) == "8.1.100"
        assert cs_sdk.pick(["9.0.100"], want) is None

    def test_disable_needs_an_exact_match(self):
        want = {"version": "8.0.100", "rollForward": "disable"}

        assert cs_sdk.pick(["8.0.101"], want) is None
        assert cs_sdk.pick(["8.0.100", "8.0.101"], want) == "8.0.100"

    def test_patch_is_the_default_and_uses_the_latest_patch_of_the_band(self):
        want = {"version": "8.0.100"}

        assert cs_sdk.pick(["8.0.103", "8.0.150"], want) == "8.0.150"
        assert cs_sdk.pick(["8.0.200"], want) is None

    def test_feature_rolls_to_the_next_band_but_not_the_next_minor(self):
        want = {"version": "8.0.100", "rollForward": "feature"}

        assert cs_sdk.pick(["8.0.205", "8.0.300"], want) == "8.0.205"
        assert cs_sdk.pick(["8.1.100"], want) is None

    def test_minor_rolls_to_the_next_minor(self):
        assert cs_sdk.pick(["8.1.100", "8.2.100"], {"version": "8.0.100", "rollForward": "minor"}) == "8.1.100"

    def test_major_rolls_to_the_next_major(self):
        assert cs_sdk.pick(["9.0.100", "10.0.100"], {"version": "8.0.100", "rollForward": "major"}) == "9.0.100"

    def test_no_file_picks_the_highest_installed(self):
        assert cs_sdk.pick(["8.0.100", "10.0.403", "9.0.200"], None) == "10.0.403"

    def test_no_version_picks_the_highest_installed(self):
        assert cs_sdk.pick(["8.0.100", "9.0.200"], {"rollForward": "disable"}) == "9.0.200"

    def test_prerelease_is_skipped_unless_allowed(self):
        want = {"version": "10.0.100", "rollForward": "latestMajor"}

        assert cs_sdk.pick(["10.0.100-preview.1.2"], want) is None
        assert cs_sdk.pick(["10.0.100-preview.1.2"], dict(want, allowPrerelease=True)) == "10.0.100-preview.1.2"

    def test_nothing_installed_gives_none(self):
        assert cs_sdk.pick([], {"version": "8.0.100"}) is None

    def test_conduit_requirement_is_met_by_403_and_500_but_not_114(self):
        want = {"version": "10.0.403", "rollForward": "latestFeature"}

        assert cs_sdk.pick(["10.0.403"], want) == "10.0.403"
        assert cs_sdk.pick(["10.0.500"], want) == "10.0.500"
        assert cs_sdk.pick(["10.0.114"], want) is None


class TestRequirements:
    def test_only_tracked_global_json_files_with_a_version_count(self):
        files = {"global.json": '{"sdk": {"version": "10.0.403", "rollForward": "latestFeature"}}',
                 "sub/global.json": '{"sdk": {"rollForward": "latestMajor"}}',
                 "node_modules/x/global.json": '{"sdk": {"version": "1.0.0"}}'}

        got = cs_sdk.requirements(list(files), files.get)

        assert got == [{"path": "global.json", "version": "10.0.403", "rollForward": "latestFeature"}]


class TestApply:
    def report(self):
        return {"host": [{"id": "dotnet", "status": "ok", "version": "10.0.114", "needs": "8.0.100", "for": ["C#"], "install": "i", "optional": False}],
                "missing": [], "self_installing": [], "languages": []}

    def test_unmet_requirement_marks_dotnet_old(self):
        report = self.report()
        reqs = [{"path": "global.json", "version": "10.0.403", "rollForward": "latestFeature"}]

        cs_sdk.apply(report, reqs, ["10.0.114"])

        assert report["host"][0]["status"] == "old"
        assert report["host"][0]["needs"] == "10.0.403 (latestFeature) for global.json"
        assert report["missing"] == ["dotnet"]

    def test_met_requirement_changes_nothing(self):
        report = self.report()
        reqs = [{"path": "global.json", "version": "10.0.403", "rollForward": "latestFeature"}]

        cs_sdk.apply(report, reqs, ["10.0.403"])

        assert report["host"][0]["status"] == "ok" and report["missing"] == []

    def test_missing_dotnet_is_left_alone(self):
        report = self.report()
        report["host"][0]["status"] = "missing"
        report["missing"] = ["dotnet"]

        cs_sdk.apply(report, [{"path": "g", "version": "10.0.403", "rollForward": "patch"}], [])

        assert report["host"][0]["status"] == "missing" and report["missing"] == ["dotnet"]


class TestProblem:
    def test_missing_dotnet_says_so(self):
        assert cs_sdk.problem([], []) == "The .NET SDK is not installed."

    def test_unmet_requirement_names_the_file_and_what_is_installed(self):
        reqs = [{"path": "global.json", "version": "10.0.403", "rollForward": "latestFeature"}]

        assert cs_sdk.problem(["10.0.114"], reqs) == (
            "The repository asks for .NET SDK 10.0.403 (latestFeature) in global.json, and this machine has 10.0.114.")

    def test_met_requirement_gives_none(self):
        assert cs_sdk.problem(["10.0.403"], [{"path": "g", "version": "10.0.403", "rollForward": "patch"}]) is None


class TestRuntimeMajors:
    def test_reads_the_core_runtime_lines_only(self):
        text = "Microsoft.AspNetCore.App 10.0.14 [/x]\nMicrosoft.NETCore.App 8.0.5 [/x]\nMicrosoft.NETCore.App 10.0.14 [/x]\n"

        assert cs_sdk.runtime_majors(text) == [8, 10]
