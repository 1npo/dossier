import json
import subprocess

import pytest

import adapters
import workarea


class FixtureAdapter(adapters.Adapter):
    name = "fixture"
    languages = ("Python",)
    expected_untracked = (".venv/**",)

    def extract(self, ctx):
        return {"entry_points": [{"path": "app.py", "kind": "script"}, {"path": ".venv/x.py"}, {"path": "ghost.py"}]}


class Node(FixtureAdapter):
    name = "node"
    loads_repo_code = True


class Mutator(FixtureAdapter):
    name = "mutator"

    def extract(self, ctx):
        (ctx.checkout / "app.py").write_text("changed\n")
        return {"entry_points": [{"path": "app.py"}]}


class Raiser(FixtureAdapter):
    name = "raiser"

    def extract(self, ctx):
        raise RuntimeError("boom\nmore")


class Second(FixtureAdapter):
    name = "second"

    def extract(self, ctx):
        return {"symbols": [{"path": "app.py"}]}


@pytest.fixture
def env(tmp_path, hygiene_repo):
    area = workarea.area_for("h", hygiene_repo.path, "r", tmp_path / "cache")
    out = tmp_path / "out"
    tree = frozenset(subprocess.run(["git", "-C", hygiene_repo.path, "ls-tree", "-r", "--name-only", hygiene_repo.main_sha],
                                    capture_output=True, text=True).stdout.split())
    co = workarea.ensure_checkout(area, hygiene_repo.path, hygiene_repo.main_sha)["path"]

    def go(adapter_list, sha=None, trusted=None, allow_ref=False, tool_versions=None):
        sha = sha or hygiene_repo.main_sha
        if sha != hygiene_repo.main_sha:
            workarea.ensure_checkout(area, hygiene_repo.path, sha)
        return adapters.run_extract(
            adapters=adapter_list, checkout=co, sha=sha, tree=tree, area=area, out=out,
            trusted=trusted or workarea.trusted(hygiene_repo.path, sha), allow_ref=allow_ref, restored={},
            treesitter=None, semgrep=None, tool_versions=tool_versions or {}, timeout=30)

    go.out = out
    go.repo = hygiene_repo
    return go


class TestRunExtract:
    def test_kept_items_are_written_and_counted(self, env):
        rec = env([FixtureAdapter()])

        data = json.loads((env.out / "extract/entry_points.json").read_text())
        assert data["adapters"]["fixture"]["items"] == [{"path": "app.py", "kind": "script"}]
        assert (rec["counts"]["paths_seen"], rec["counts"]["dropped_expected"], rec["counts"]["dropped_unexpected"]) == (3, 1, 1)
        assert rec["status"] == "ok"

    def test_same_key_is_reused(self, env):
        env([FixtureAdapter()])

        rec = env([FixtureAdapter()])

        assert rec["status"] == "reused"

    def test_new_adapter_version_runs_again(self, env):
        env([FixtureAdapter()])

        class V2(FixtureAdapter):
            version = "2"

        assert env([V2()])["status"] == "ok"

    def test_tool_version_change_runs_again(self, env):
        class Tooled(FixtureAdapter):
            tools = ("semgrep",)

        env([Tooled()], tool_versions={"semgrep": "1"})

        assert env([Tooled()], tool_versions={"semgrep": "2"})["status"] == "ok"

    def test_untrusted_ref_skips_repo_code_adapter_without_allow_ref(self, env):
        rec = env([Node()], sha=env.repo.feature_sha)

        assert rec["status"] == "skipped" and "--allow-ref" in rec["reason"]

    def test_untrusted_ref_runs_with_allow_ref(self, env):
        assert env([Node()], sha=env.repo.feature_sha, allow_ref=True)["status"] == "ok"

    def test_adapter_that_changes_tracked_files_fails_the_step(self, env):
        rec = env([Mutator()])

        assert rec["status"] == "failed" and "clean copy changed" in rec["reason"]
        assert not (env.out / "extract").exists()

    def test_raising_adapter_fails_but_others_still_run(self, env):
        rec = env([Raiser(), Second()])

        statuses = {r["name"]: r["status"] for r in rec["details"]["adapters"]}
        assert statuses == {"raiser": "failed", "second": "ok"} and rec["status"] == "ok"
        assert rec["details"]["adapters"][0]["reason"] == "boom"

    def test_no_adapters_is_skipped_with_a_reason(self, env):
        rec = env([])

        assert rec["status"] == "skipped" and rec["reason"] == adapters.NO_EXTRACTORS
