import pytest

import cs_sdk
import js_tools
import restore
import sandbox
import toolcheck

TOOLS = {"restore": [
    {"ecosystem": "python", "lockfile": "uv.lock", "command": ["uv", "sync", "--frozen"], "enabled": True},
    {"ecosystem": "npm", "lockfile": "package-lock.json", "command": ["npm", "ci"], "enabled": False},
]}
NODE_TOOLS = {"restore": [
    *TOOLS["restore"][:1],
    {"ecosystem": "npm", "lockfile": "package-lock.json", "nested": True, "enabled": True, "command": ["npm", "ci"]},
    {"ecosystem": "yarn", "lockfile": "yarn.lock", "nested": True, "enabled": True, "auth": "npm",
     "command": ["node", "{js_tools}/yarn.js", "install", "--frozen-lockfile"], "berry_command": ["node", "{js_tools}/berry.js", "--immutable"]},
    {"ecosystem": "pnpm", "lockfile": "pnpm-lock.yaml", "nested": True, "enabled": True, "auth": "npm",
     "command": ["node", "{js_tools}/pnpm.mjs", "install", "--store-dir", "{pnpm_store}"]},
]}
NUGET_TOOLS = {"restore": [
    *NODE_TOOLS["restore"][:2],
    {"ecosystem": "nuget", "lockfile": "packages.lock.json", "nested": True, "enabled": True,
     "command": ["dotnet", "restore", "{project}", "--locked-mode"]},
]}
TRUSTED = {"trusted": True, "why": "tag v1", "default_branch": None}
UNTRUSTED = {"trusted": False, "why": "not a tag and not on the default branch main", "default_branch": "main"}
PLAN = [{"ecosystem": "python", "lockfile": "uv.lock", "command": ["x"], "enabled": True}]


def decide(plans=PLAN, state=None, answer=None, no_restore=False, trust=TRUSTED, allow_ref=False):
    return restore.decide(plans, state=state or {}, answer=answer, no_restore=no_restore, trust=trust, allow_ref=allow_ref)


class TestPlans:
    def test_only_root_lockfiles_in_the_tree(self):
        got = restore.plans(frozenset({"uv.lock", "sub/package-lock.json"}), TOOLS)

        assert [p["ecosystem"] for p in got] == ["python"]


class TestNestedPlans:
    def test_a_nested_lockfile_gives_a_plan_with_its_folder(self):
        got = restore.plans(frozenset({"apps/web/yarn.lock", "apps/api/yarn.lock", "package.json"}), NODE_TOOLS)

        assert [(p["ecosystem"], p["dir"], p["lockfile"]) for p in got] == [("yarn", "apps/api", "apps/api/yarn.lock"),
                                                                           ("yarn", "apps/web", "apps/web/yarn.lock")]

    def test_a_root_lockfile_has_an_empty_folder_and_python_plans_do_too(self):
        got = restore.plans(frozenset({"uv.lock", "package-lock.json"}), NODE_TOOLS)

        assert [(p["ecosystem"], p["dir"]) for p in got] == [("python", ""), ("npm", "")]

    def test_python_lockfile_below_the_root_gives_none(self):
        assert restore.plans(frozenset({"sub/uv.lock"}), NODE_TOOLS) == []

    def test_lockfiles_inside_vendored_folders_are_ignored(self):
        assert restore.plans(frozenset({"node_modules/x/package-lock.json", "a/dist/yarn.lock"}), NODE_TOOLS) == []

    def test_auth_defaults_to_the_ecosystem_and_can_be_shared(self):
        got = restore.plans(frozenset({"uv.lock", "yarn.lock", "pnpm-lock.yaml"}), NODE_TOOLS)

        assert {p["ecosystem"]: p["auth"] for p in got} == {"python": "python", "yarn": "npm", "pnpm": "npm"}

    def test_berry_lockfile_picks_the_berry_command(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "a/yarn.lock").write_text("__metadata:\n  version: 8\n")
        (tmp_path / "b").mkdir()
        (tmp_path / "b/yarn.lock").write_text("# yarn lockfile v1\n")

        got = restore.plans(frozenset({"a/yarn.lock", "b/yarn.lock"}), NODE_TOOLS, tmp_path)

        assert [p["command"][1] for p in got] == ["{js_tools}/berry.js", "{js_tools}/yarn.js"]

    def test_without_a_checkout_yarn_is_classic(self):
        assert restore.plans(frozenset({"yarn.lock"}), NODE_TOOLS)[0]["command"][1] == "{js_tools}/yarn.js"


class TestNugetPlans:
    def test_a_lock_file_in_three_folders_gives_three_plans(self):
        tree = frozenset({"a/packages.lock.json", "a/a.csproj", "b/packages.lock.json", "b/b.csproj", "c/packages.lock.json", "c/c.csproj"})

        got = restore.plans(tree, NUGET_TOOLS)

        assert [(p["ecosystem"], p["dir"]) for p in got] == [("nuget", "a"), ("nuget", "b"), ("nuget", "c")]

    def test_the_plan_lists_the_project_files_beside_its_lock_file(self):
        tree = frozenset({"a/packages.lock.json", "a/a.csproj", "a/b.fsproj", "z/z.csproj", "a/sub/s.csproj"})

        got = restore.plans(tree, NUGET_TOOLS)

        assert got[0]["projects"] == ["a/a.csproj", "a/b.fsproj"]

    def test_plans_without_the_token_carry_no_project_list(self):
        got = restore.plans(frozenset({"uv.lock", "package-lock.json"}), NUGET_TOOLS)

        assert all("projects" not in p for p in got)


class TestRestored:
    def result(self, eco, status, dir_=""):
        return {"ecosystem": eco, "status": status, "dir": dir_}

    def test_an_ecosystem_is_restored_only_when_every_plan_of_it_succeeded(self):
        got = restore.restored([self.result("yarn", "ok", "a"), self.result("yarn", "failed", "b"), self.result("npm", "ok")])

        assert got == {"yarn": False, "npm": True}

    def test_skipped_results_are_left_out(self):
        assert restore.restored([self.result("nuget", "skipped")]) == {}


class TestRunNested:
    @pytest.fixture
    def stage(self, tmp_path, monkeypatch):
        area, co = tmp_path / "cache" / "repo", tmp_path / "co"
        (co / "apps/web").mkdir(parents=True)
        tools = tmp_path / "tools"
        tools.mkdir()
        monkeypatch.setattr(js_tools, "ensure_installed", lambda run, cache_root, timeout: tools)
        return area, co, tools

    def plan(self, command, dir_="apps/web", eco="yarn"):
        return [{"ecosystem": eco, "lockfile": "x", "command": command, "enabled": True, "dir": dir_, "auth": "npm"}]

    def test_runs_in_the_project_folder_and_expands_the_tool_folder(self, stage):
        area, co, tools = stage

        res = restore.run(self.plan(["sh", "-c", 'pwd > "$HOME/where"; echo "$0" > "$HOME/tok"', "{js_tools}/yarn.js"]),
                          area=area, checkout=co, timeout=30)

        assert res[0]["status"] == "ok" and res[0]["dir"] == "apps/web"
        assert (area / "home/where").read_text().strip() == str(co / "apps/web")
        assert (area / "home/tok").read_text().strip() == f"{tools}/yarn.js"

    def test_pnpm_store_token_points_inside_the_area(self, stage):
        area, co, _ = stage

        restore.run(self.plan(["sh", "-c", 'echo "$0" > "$HOME/tok"', "{pnpm_store}"], eco="pnpm"), area=area, checkout=co, timeout=30)

        assert (area / "home/tok").read_text().strip() == str(area / "cache/pnpm")

    def test_failure_names_the_folder_but_a_root_failure_does_not(self, stage):
        area, co, _ = stage

        nested = restore.run(self.plan(["sh", "-c", "exit 3"]), area=area, checkout=co, timeout=30)[0]["reason"]
        root = restore.run(self.plan(["sh", "-c", "exit 3"], dir_=""), area=area, checkout=co, timeout=30)[0]["reason"]

        assert nested.endswith(" (in apps/web)") and "exit 3" in nested
        assert "(in " not in root and root.endswith(".")

    def test_a_package_manager_that_cannot_be_installed_fails_the_plan(self, stage, monkeypatch):
        area, co, _ = stage

        def broken(run, cache_root, timeout):
            raise js_tools.ToolError("npm ci failed")
        monkeypatch.setattr(js_tools, "ensure_installed", broken)

        res = restore.run(self.plan(["node", "{js_tools}/yarn.js"]), area=area, checkout=co, timeout=30)

        assert res[0]["status"] == "failed" and "npm ci failed" in res[0]["reason"]

    def test_the_tool_folder_is_installed_once_for_several_plans(self, stage, monkeypatch):
        area, co, tools = stage
        calls = []
        monkeypatch.setattr(js_tools, "ensure_installed", lambda run, cache_root, timeout: calls.append(1) or tools)
        (co / "apps/api").mkdir()

        restore.run(self.plan(["true", "{js_tools}"]) + self.plan(["true", "{js_tools}"], dir_="apps/api"), area=area, checkout=co, timeout=30)

        assert len(calls) == 1

    def test_plans_without_a_tool_token_never_install_the_tools(self, stage, monkeypatch):
        area, co, _ = stage
        monkeypatch.setattr(js_tools, "ensure_installed", lambda *a, **k: pytest.fail("installed"))

        res = restore.run(self.plan(["true"], eco="npm"), area=area, checkout=co, timeout=30)

        assert res[0]["status"] == "ok"


class TestRunNuget:
    @pytest.fixture
    def stage(self, tmp_path, monkeypatch):
        area, co = tmp_path / "cache" / "repo", tmp_path / "co"
        (co / "src/App").mkdir(parents=True)
        monkeypatch.setattr(cs_sdk, "problem_for", lambda checkout, path=None: None)
        return area, co

    def plan(self, command, projects=("src/App/App.csproj",), dir_="src/App"):
        return [{"ecosystem": "nuget", "lockfile": "src/App/packages.lock.json", "command": command, "enabled": True,
                 "dir": dir_, "auth": "nuget", "projects": list(projects)}]

    def test_the_token_becomes_the_one_project_file_name_and_the_command_runs_in_its_folder(self, stage):
        area, co = stage

        res = restore.run(self.plan(["sh", "-c", 'pwd > "$HOME/where"; echo "$0" > "$HOME/tok"', "{project}"]), area=area, checkout=co, timeout=30)

        assert res[0]["status"] == "ok"
        assert (area / "home/tok").read_text().strip() == "App.csproj"
        assert (area / "home/where").read_text().strip() == str(co / "src/App")

    def test_two_project_files_beside_one_lock_file_fail_the_plan(self, stage):
        area, co = stage

        res = restore.run(self.plan(["false", "{project}"], projects=("src/App/a.csproj", "src/App/b.csproj")), area=area, checkout=co, timeout=30)

        assert res[0]["status"] == "failed"
        assert res[0]["reason"].startswith("The lock file src/App/packages.lock.json is not beside exactly one project file, so it was not used.")

    def test_no_project_file_fails_the_plan(self, stage):
        area, co = stage

        res = restore.run(self.plan(["false", "{project}"], projects=()), area=area, checkout=co, timeout=30)

        assert res[0]["status"] == "failed" and "not beside exactly one project file" in res[0]["reason"]

    def test_an_sdk_problem_skips_every_nuget_plan_and_runs_nothing(self, stage, monkeypatch):
        area, co = stage
        monkeypatch.setattr(cs_sdk, "problem_for", lambda checkout, path=None: "The .NET SDK is not installed.")
        plans = self.plan(["sh", "-c", 'touch "$HOME/ran"', "{project}"]) * 2

        res = restore.run(plans, area=area, checkout=co, timeout=30)

        assert [(r["status"], r["reason"]) for r in res] == [("skipped", "The .NET SDK is not installed.")] * 2
        assert not (area / "home/ran").exists()

    def test_the_sdk_is_checked_once_and_not_for_other_ecosystems(self, stage, monkeypatch):
        area, co = stage
        calls = []
        monkeypatch.setattr(cs_sdk, "problem_for", lambda checkout, path=None: calls.append(1))
        other = [{"ecosystem": "python", "lockfile": "uv.lock", "command": ["true"], "enabled": True, "dir": ""}]

        restore.run(other, area=area, checkout=co, timeout=30)
        restore.run(self.plan(["true"]) * 2, area=area, checkout=co, timeout=30)

        assert len(calls) == 1

    def test_a_workload_error_gets_the_workload_reason(self, stage):
        area, co = stage

        res = restore.run(self.plan(["sh", "-c", "echo 'error NETSDK1147: To build this project, workloads must be installed' >&2; exit 1", "{project}"]),
                          area=area, checkout=co, timeout=30)

        assert res[0]["status"] == "failed"
        assert res[0]["reason"] == "Restoring src/App/App.csproj needs a .NET workload, and dossier does not install workloads. (in src/App)"

    def test_a_feed_that_refuses_credentials_names_registry_auth_nuget(self, stage):
        area, co = stage

        res = restore.run(self.plan(["sh", "-c", "echo 'error NU1301: Unable to load the service index' >&2; exit 1", "{project}"]),
                          area=area, checkout=co, timeout=30)

        assert "registry_auth.nuget" in res[0]["reason"]


class TestDecide:
    def test_no_plans_skips(self):
        assert "no lockfile" in decide(plans=[])["reason"]

    def test_no_restore_skips(self):
        assert "--no-restore" in decide(no_restore=True)["reason"]

    def test_untrusted_ref_skips_without_allow_ref(self):
        d = decide(trust=UNTRUSTED, answer="yes")

        assert (d["action"], "--allow-ref" in d["reason"]) == ("skip", True)

    def test_untrusted_ref_runs_with_allow_ref(self):
        assert decide(trust=UNTRUSTED, answer="yes", allow_ref=True)["action"] == "run"

    def test_answer_yes_runs_and_is_stored(self):
        d = decide(answer="yes")

        assert (d["action"], d["store"]) == ("run", "yes")

    def test_answer_no_skips_and_is_stored(self):
        d = decide(answer="no")

        assert (d["action"], d["store"]) == ("skip", "no")

    def test_stored_no_skips_with_hint(self):
        d = decide(state={"restore": {"answer": "no"}})

        assert d["action"] == "skip" and "--restore yes" in d["reason"]

    def test_stored_yes_covering_the_ecosystem_runs(self):
        assert decide(state={"restore": {"answer": "yes", "ecosystems": ["python"]}})["action"] == "run"

    def test_stored_yes_not_covering_a_new_ecosystem_asks_again(self):
        assert decide(state={"restore": {"answer": "yes", "ecosystems": ["npm"]}})["action"] == "ask"

    def test_nothing_stored_asks(self):
        assert decide()["action"] == "ask"


class TestNestedPythonPlans:
    def test_a_uv_lock_below_the_root_gives_a_plan_with_its_folder(self):
        got = restore.plans(frozenset({"backend/uv.lock"}), toolcheck.load_tools())

        assert [(p["ecosystem"], p["dir"], p["lockfile"]) for p in got] == [("python", "backend", "backend/uv.lock")]

    def test_a_root_uv_lock_is_unchanged(self):
        got = restore.plans(frozenset({"uv.lock"}), toolcheck.load_tools())

        assert [(p["ecosystem"], p["dir"], p["lockfile"], p["command"]) for p in got] == [("python", "", "uv.lock", ["uv", "sync", "--frozen"])]

    def test_other_ecosystems_keep_their_nesting_rules(self):
        entries = {r["ecosystem"]: bool(r.get("nested")) for r in toolcheck.load_tools()["restore"]}

        assert entries == {"python": True, "npm": True, "yarn": True, "pnpm": True, "nuget": True}

    def test_a_uv_lock_in_a_vendored_folder_is_ignored(self):
        assert restore.plans(frozenset({"node_modules/x/uv.lock"}), toolcheck.load_tools()) == []
