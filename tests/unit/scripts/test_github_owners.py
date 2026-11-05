import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import github_owners

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "github"
SHA = "a" * 40


def saved(name):
    return (FIXTURES / f"{name}.json").read_text()


class FakeRun:
    """Answers each gh call with the next canned (stdout, returncode, timed_out)."""

    def __init__(self, tmp_path, *answers):
        self.tmp, self.answers, self.calls = tmp_path, list(answers), []

    def __call__(self, cmd, *, stage, timeout, profile):
        self.calls.append((cmd, stage, profile))
        out, code, timed_out = self.answers.pop(0)
        n = len(self.calls)
        so, se = self.tmp / f"{n}.out", self.tmp / f"{n}.err"
        so.write_text(out)
        se.write_text("boom: not logged in\n" if code else "")
        return SimpleNamespace(stdout=so, stderr=se, returncode=None if timed_out else code, timed_out=timed_out)


def lookup(tmp_path, name, cache=None):
    run = FakeRun(tmp_path, (saved(name), 0, False))
    got = github_owners.lookup("o/r", [SHA], run, {} if cache is None else cache, 60)
    return got, run


class TestSlug:
    def test_reads_owner_and_name_from_the_remote(self):
        assert github_owners.slug({"web_base": "https://github.com/1npo/encamp"}) == "1npo/encamp"

    def test_other_hosts_have_none(self):
        assert github_owners.slug({"web_base": "https://gitlab.com/a/b"}) is None
        assert github_owners.slug({"web_base": None}) is None


class TestLookup:
    def test_one_approval(self, tmp_path):
        got, _ = lookup(tmp_path, "one_approval")

        assert got[SHA] == {"number": 7, "approver": "rae", "merged_by": "amy"}

    def test_the_last_approval_wins(self, tmp_path):
        got, _ = lookup(tmp_path, "two_approvals")

        assert got[SHA]["approver"] == "sol"

    def test_a_bot_reviewer_does_not_count(self, tmp_path):
        got, _ = lookup(tmp_path, "approval_by_bot_then_human")

        assert got[SHA]["approver"] == "sol"

    def test_no_approval_keeps_the_human_who_merged(self, tmp_path):
        got, _ = lookup(tmp_path, "merged_by_human_no_approval")

        assert got[SHA] == {"number": 10, "approver": None, "merged_by": "amy"}

    def test_merged_by_a_bot_with_no_approval_has_no_owner(self, tmp_path):
        got, _ = lookup(tmp_path, "merged_by_bot_no_approval")

        assert got[SHA] == {"number": 11, "approver": None, "merged_by": None}

    def test_no_pull_request_is_left_out(self, tmp_path):
        got, _ = lookup(tmp_path, "no_pull_request")

        assert got == {} and got.error is None

    def test_an_unmerged_pull_request_is_ignored(self, tmp_path):
        got, _ = lookup(tmp_path, "unmerged_only")

        assert got == {}

    def test_two_pull_requests_use_the_lowest_merged_number(self, tmp_path):
        got, _ = lookup(tmp_path, "two_pull_requests")

        assert got[SHA]["number"] == 12 and got[SHA]["approver"] == "early"

    def test_calls_gh_through_the_github_profile_with_no_token_in_the_command(self, tmp_path):
        _, run = lookup(tmp_path, "one_approval")

        cmd, stage, profile = run.calls[0]
        assert cmd[:3] == ["gh", "api", "graphql"] and (stage, profile) == ("github", "github")
        assert "token" not in " ".join(cmd).lower()

    def test_results_with_a_pull_request_are_cached_and_not_asked_again(self, tmp_path):
        cache = {}
        lookup(tmp_path, "one_approval", cache)
        run = FakeRun(tmp_path)

        got = github_owners.lookup("o/r", [SHA], run, cache, 60)

        assert got[SHA]["number"] == 7 and run.calls == []

    def test_a_gh_failure_keeps_earlier_batches_and_reports_the_rest(self, tmp_path):
        shas = [f"{i:040x}" for i in range(github_owners.BATCH + 2)]
        first = json.loads(saved("one_approval"))
        run = FakeRun(tmp_path, (json.dumps(first), 0, False), ("", 1, False))

        got = github_owners.lookup("o/r", shas, run, {}, 60)

        assert got[shas[0]]["number"] == 7 and got.error == "boom: not logged in"
        assert got.unread == shas[github_owners.BATCH:]

    def test_a_timeout_is_an_error_not_a_crash(self, tmp_path):
        run = FakeRun(tmp_path, ("", 0, True))

        got = github_owners.lookup("o/r", [SHA], run, {}, 60)

        assert got == {} and got.error == "gh took too long" and got.unread == [SHA]

    def test_no_time_left_asks_nothing(self, tmp_path):
        run = FakeRun(tmp_path)

        got = github_owners.lookup("o/r", [SHA], run, {}, 0)

        assert run.calls == [] and got.unread == [SHA] and got.error

    def test_only_full_hex_shas_reach_the_query(self, tmp_path):
        run = FakeRun(tmp_path, (saved("no_pull_request"), 0, False))

        github_owners.lookup("o/r", ['abc"){evil'], run, {}, 60)

        assert run.calls == []


class TestLogins:
    def test_maps_each_commit_to_its_author_login(self, tmp_path):
        run = FakeRun(tmp_path, (saved("one_approval"), 0, False))

        got = github_owners.logins("o/r", [SHA], run, 60)

        assert got == {SHA: "bot-author"}

    def test_failure_returns_what_it_has(self, tmp_path):
        run = FakeRun(tmp_path, ("", 1, False))

        assert github_owners.logins("o/r", [SHA], run, 60) == {}
