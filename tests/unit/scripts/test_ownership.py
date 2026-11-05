from types import SimpleNamespace

import history
import ownership


def commit(sha, who, parents=("p",)):
    return history.Commit(sha, who, f"{who}@x.io", "2026-01-01T00:00:00+00:00", tuple(parents), "m", ())


def folded(*pairs):
    commits = [commit(sha, who) for sha, who in pairs]
    return SimpleNamespace(commits=commits, author_of={sha: who for sha, who in pairs})


class TestOwnerOf:
    def test_one_human_owns_every_commit_including_bots(self):
        assert ownership.owner_of("dependabot", "bot", None, "ann") == "ann"
        assert ownership.owner_of("claude", "agent", "bob", "ann") == "ann"

    def test_a_human_author_owns_their_own_commit(self):
        assert ownership.owner_of("bob", "human", "ann", None) == "bob"

    def test_an_agent_commit_goes_to_the_human_who_approved_its_pull_request(self):
        assert ownership.owner_of("claude", "agent", "ann", None) == "ann"
        assert ownership.owner_of("dependabot", "bot", "ann", None) == "ann"

    def test_an_agent_commit_with_no_pull_request_belongs_to_its_author(self):
        assert ownership.owner_of("claude", "agent", None, None) == "claude"

    def test_no_humans_at_all_leaves_everything_with_the_author(self):
        types = {"claude": "agent", "dependabot": "bot"}

        got = ownership.apply(folded(("a", "claude"), ("b", "dependabot")), types, {})

        assert got == {"a": "claude", "b": "dependabot"}


class TestSoleHuman:
    def test_exactly_one_human(self):
        assert ownership.sole_human_of({"ann": "human", "claude": "agent"}) == "ann"

    def test_two_humans_or_none(self):
        assert ownership.sole_human_of({"ann": "human", "bob": "human"}) is None
        assert ownership.sole_human_of({"claude": "agent"}) is None


class TestApply:
    def test_two_humans_use_the_pull_request_owner_for_agent_commits(self):
        types = {"ann": "human", "bob": "human", "claude": "agent"}

        got = ownership.apply(folded(("a", "ann"), ("b", "bob"), ("c", "claude"), ("d", "claude")), types, {"c": "bob"})

        assert got == {"a": "ann", "b": "bob", "c": "bob", "d": "claude"}

    def test_an_approver_who_never_committed_can_own(self):
        types = {"ann": "human", "bob": "human", "claude": "agent", "github:zed": "human"}

        got = ownership.apply(folded(("c", "claude")), types, {"c": "github:zed"})

        assert got == {"c": "github:zed"}
