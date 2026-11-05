import functools
from pathlib import Path

import pytest

import gather
import history
import sandbox


@pytest.fixture
def world(tmp_path, history_repo):
    top = str(history_repo)
    facts, _ = gather.collect(top, "HEAD", 400_000, None)
    sha = facts["repo"]["sha"]
    area = tmp_path / "area"
    run = functools.partial(sandbox.run, area=area, cwd=Path(top))

    def collect(handed=None, timeout=60):
        return history.collect(top, sha, run, handed or facts["history_input"], timeout)

    collect.facts, collect.top, collect.sha, collect.run = facts, top, sha, run
    return collect


def items(data, kind):
    return [i for i in history.items_of(data) if i["kind"] == kind]


class TestCollect:
    def test_meta_is_ok_on_a_full_clone(self, world):
        meta = history.meta_of(world())

        assert meta["status"] == "ok" and meta["reasons"] == [] and meta["shallow"] is False
        assert meta["commits_seen"] == meta["commits_total"]
        assert meta["as_of"] == "2026-06-01"

    def test_files_follow_a_rename_and_count_each_commit(self, world):
        files = {f["path"]: f for f in items(world(), "file")}

        assert files["src/d2.py"]["commits"] == 2 and "src/d.py" not in files
        assert files["src/a.py"]["commits"] == 4 and files["src/a.py"]["authors"] == {"ann@x.io": 3, "bob@x.io": 1}

    def test_files_changed_together_make_pairs(self, world):
        pairs = {(p["a"], p["b"]): p for p in items(world(), "pair")}

        assert pairs[("src/a.py", "src/b.py")]["co_commits"] == 3
        assert pairs[("src/a.py", "src/c.py")]["share"] == round(100 * 3 / 3)

    def test_people_carry_type_and_assisted_count(self, world):
        people = {p["name"]: p for p in items(world(), "person")}

        assert people["Claude"]["type"] == "agent" and people["dependabot[bot]"]["type"] == "bot"
        assert people["Bob Ray"]["assisted"] == 1 and people["Ann Lee"]["assisted"] == 0

    def test_assistant_item_counts_marked_human_commits_and_their_files(self, world):
        assistant = items(world(), "assistant")

        assert assistant == [{"kind": "assistant", "path": "", "name": "Claude", "commits": 1, "files": {"src/a.py": 1}}]

    def test_bulk_commit_is_listed_and_credits_no_file(self, world, monkeypatch):
        monkeypatch.setattr(gather, "BULK_FILES", 2)

        data = world()

        assert [b["subject"] for b in items(data, "bulk")] == ["feat: step 3", "feat: step 2", "feat: step 1"]
        assert items(data, "bulk")[0]["files"] == 3 and items(data, "bulk")[0]["author"] == "Ann Lee"
        assert "src/c.py" not in {f["path"] for f in items(data, "file")}

    def test_blame_covers_every_file_on_a_full_clone(self, world):
        meta = history.meta_of(world())

        assert meta["blame_done"] == meta["blame_total"] > 0

    def test_write_puts_the_envelope_where_candidates_load_finds_it(self, world, tmp_path):
        import candidates
        data = world()

        history.write(tmp_path / "out", data)

        assert len(candidates.load(tmp_path / "out")["history"]) == len(history.items_of(data))


class TestWorkflowAndBranches:
    def test_six_workflow_rows_in_spec_order(self, world):
        rows = items(world(), "workflow")

        assert [r["convention"] for r in rows] == ["branch naming and strategy", "merge style", "commit message style",
                                                  "typical PR size", "review rate", "release cadence"]
        assert rows[0]["observed"] == "Default branch main. Most common prefixes: feat (1)."
        assert rows[5]["observed"] == "One tag." and rows[5]["evidence"] == "Newest tag v1.0 on 2025-07-01."

    def test_merge_size_is_measured_against_the_first_parent(self, world):
        row = items(world(), "workflow")[3]

        assert row["observed"] == "About 1 files and 1 changed lines per merge (median)."

    def test_remote_branch_has_ahead_and_behind_against_the_pinned_commit(self, world):
        branches = items(world(), "branch")

        assert [(b["ref"], b["ahead"], b["behind"], b["remote"]) for b in branches] == [("origin/feat-y", 0, 1, True)]
        assert branches[0]["author"] == "Bob Ray"

    def test_head_and_default_branch_refs_are_left_out(self, world):
        world.run(["git", "update-ref", "refs/remotes/origin/main", world.sha], stage="t", timeout=30, profile="tool")
        world.run(["git", "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main"], stage="t", timeout=30, profile="tool")

        branches = items(world(), "branch")

        assert [b["ref"] for b in branches] == ["origin/feat-y"]

    def test_local_branches_are_used_only_when_there_are_no_remote_ones(self, world):
        world.run(["git", "update-ref", "-d", "refs/remotes/origin/feat-y"], stage="t", timeout=30, profile="tool")

        branches = items(world(), "branch")

        assert [(b["ref"], b["remote"]) for b in branches] == [("feat/x", False)]


class TestMarkers:
    def test_marker_gets_an_id_and_a_group(self, world):
        found = items(world(), "marker")

        assert [(m["path"], m["line"], m["rule"]) for m in found] == [("src/x.py", 1, "marker.hack")]
        assert found[0]["id"].startswith("mk-") and found[0]["group"].startswith("mkg-")

    def test_ids_do_not_change_when_the_line_moves(self, world):
        handed = dict(world.facts["history_input"])
        before = items(world(handed), "marker")[0]["id"]
        moved = [{**m, "line": m["line"] + 5, "end_line": m["end_line"] + 5} for m in handed["markers"]]

        after = items(world({**handed, "markers": moved}), "marker")[0]["id"]

        assert before == after

    def test_decision_documents_and_todos_come_from_the_hand_over(self, world):
        handed = {**world.facts["history_input"], "tree": ["docs/adr/1.md"], "todos": [{"kind": "todo", "path": "a.py", "count": 2}]}

        data = world(handed)

        assert [d["path"] for d in items(data, "decision-doc")] == ["docs/adr/1.md"]
        assert items(data, "todo") == [{"kind": "todo", "path": "a.py", "count": 2}]


FIELDS = {
    "meta": {"status", "reasons", "commits_seen", "commits_total", "shallow", "stopped_early", "blame_done", "blame_total", "as_of",
             "window_from", "pairs_total", "bulk_commits", "owner_rule", "owner_status", "owner_reason", "prs_found"},
    "file": {"lines", "commits", "commits_12m", "lines_changed", "lines_changed_12m", "last_changed", "authors", "blame", "owners", "owner_lines"},
    "pair": {"a", "b", "co_commits", "commits_a", "commits_b", "share"},
    "person": {"person", "name", "type", "commits", "commits_12m", "assisted", "first", "last", "aliases", "owned_commits", "owned_lines", "username"},
    "bulk": {"sha", "files", "author", "date", "subject"},
    "branch": {"ref", "sha", "date", "ahead", "behind", "author", "remote"},
    "workflow": {"convention", "observed", "evidence", "commits"},
    "marker": {"id", "group", "line", "end_line", "rule", "snippet"},
    "assistant": {"name", "commits", "files"},
    "todo": {"count"},
    "decision-doc": set(),
    "long-commit": {"sha", "subject", "lines", "files"},
}
ID_KEYED = {"authors", "blame", "owners", "owner_lines"}


class TestShape:
    @pytest.fixture
    def data(self, world, monkeypatch):
        handed = {**world.facts["history_input"], "tree": ["docs/adr/1.md"], "todos": [{"kind": "todo", "path": "a.py", "count": 2}]}
        data = world(handed)
        monkeypatch.setattr(gather, "BULK_FILES", 2)
        bulk = [i for i in history.items_of(world(handed)) if i["kind"] == "bulk"]
        data["adapters"]["git"]["items"] += bulk
        return data

    def test_every_kind_appears_with_exactly_its_fields(self, data):
        seen = {}
        for it in history.items_of(data):
            seen.setdefault(it["kind"], set(it) - {"kind", "path"})

        assert seen == FIELDS

    def test_candidates_load_returns_the_items(self, data, tmp_path):
        import candidates
        history.write(tmp_path / "o", data)

        assert candidates.load(tmp_path / "o")["history"] == history.items_of(data)

    def test_no_email_outside_the_identity_fields(self, data):
        import json
        stripped = []
        for it in history.items_of(data):
            it = {k: v for k, v in it.items() if k not in ID_KEYED | {"person", "aliases"}}
            stripped.append(it)

        assert "@" not in json.dumps(stripped)


def person(data, name):
    return next(p for p in items(data, "person") if p["name"] == name)


class TestOwnership:
    def test_two_humans_and_no_github_remote_fall_back_to_authors_with_a_reason(self, world):
        data = world()

        meta = history.meta_of(data)
        assert (meta["owner_rule"], meta["owner_status"], meta["owner_reason"]) == ("authors", "partial", "the repository is not on GitHub")
        assert person(data, "Claude")["owned_commits"] == 1

    def test_one_human_owns_everything_and_gh_is_never_called(self, world):
        handed = {**world.facts["history_input"], "ctype": {**world.facts["history_input"]["ctype"], "bob@x.io": "agent"}}
        calls = []

        def run(cmd, **kw):
            calls.append(cmd[0])
            return world.run(cmd, **kw)

        data = history.collect(world.top, world.sha, run, handed, 60)

        assert history.meta_of(data)["owner_rule"] == "one-human" and "gh" not in calls
        assert person(data, "Claude")["owned_commits"] == 0 and person(data, "Bob Ray")["owned_commits"] == 0
        assert person(data, "Ann Lee")["owned_commits"] == sum(p["commits"] for p in items(data, "person"))
        files = {f["path"]: f for f in items(data, "file")}
        assert set(files["src/a.py"]["owners"]) == {"ann@x.io"} and set(files["src/a.py"]["owner_lines"]) == {"ann@x.io"}

    def fake_gh(self, world, approver="ann-login"):
        import json, re

        def author_login(sha):
            _, out = history.workflow.git(world.run, ["log", "-1", "--format=%ae", sha], 30)
            return out.decode().split("@")[0] + "-login"

        def run(cmd, **kw):
            if cmd[0] != "gh":
                return world.run(cmd, **kw)
            query = cmd[-1]
            shas = re.findall(r'c(\d+):object\(expression:"([0-9a-f]{40})"', query)
            repo = {}
            for i, sha in shas:
                node = {"author": {"user": {"login": author_login(sha)}}}
                if "associatedPullRequests" in query:
                    node["associatedPullRequests"] = {"nodes": [{"number": int(i) + 1, "merged": True, "mergedBy": None,
                                                                 "reviews": {"nodes": [{"author": {"login": approver, "__typename": "User"}}]}}]}
                repo[f"c{i}"] = node
            out = world.run(["true"], stage="fake", timeout=5, profile="tool")
            out.stdout.write_text(json.dumps({"data": {"repository": repo}}))
            return out
        return run

    def test_agent_and_bot_commits_belong_to_the_approver(self, world):
        handed = {**world.facts["history_input"], "remote": {"web_base": "https://github.com/o/r"}}

        data = history.collect(world.top, world.sha, self.fake_gh(world), handed, 60, {}, 60)

        meta = history.meta_of(data)
        assert (meta["owner_rule"], meta["owner_status"], meta["prs_found"]) == ("pull-requests", "ok", 2)
        assert person(data, "Claude")["owned_commits"] == 0 and person(data, "Ann Lee")["owned_commits"] == 7
        assert person(data, "Ann Lee")["username"] == "ann-login"

    def test_an_approver_nobody_knows_becomes_a_person_with_no_commits(self, world):
        handed = {**world.facts["history_input"], "remote": {"web_base": "https://github.com/o/r"}}

        data = history.collect(world.top, world.sha, self.fake_gh(world, approver="stranger"), handed, 60, {}, 60)

        stranger = next(p for p in items(data, "person") if p["person"] == "github:stranger")
        assert (stranger["name"], stranger["type"], stranger["commits"], stranger["owned_commits"]) == ("stranger", "human", 0, 2)
