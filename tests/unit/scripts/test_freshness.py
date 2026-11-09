"""workarea.freshness and render.freshness_tile (D6), with a fake `run` and fake git answers."""
import types
from pathlib import Path

import pytest

import render
import workarea

SHA = "a" * 40
NEW = "b" * 40


class FakeGit:
    """Answers `workarea.git` and `workarea._ok` from a table: arguments (after the repository) -> output or bool."""

    def __init__(self, answers=None, present=()):
        self.answers, self.present = answers or {}, set(present)

    def git(self, cwd, *args, check=True):
        return self.answers.get(args, "")

    def ok(self, cwd, *args):
        if args[:2] == ("cat-file", "-e"):
            return args[2][:40] in self.present
        return bool(self.answers.get(args))


@pytest.fixture
def fake(monkeypatch):
    def make(answers=None, present=(SHA,)):
        g = FakeGit(answers, present)
        monkeypatch.setattr(workarea, "git", g.git)
        monkeypatch.setattr(workarea, "_ok", g.ok)
        return g
    return make


def runner(tmp_path, out="", code=0, timed_out=False, calls=None):
    def run(cmd, stage="freshness", timeout=15):
        if calls is not None:
            calls.append(cmd)
        p = Path(tmp_path) / f"out{len(calls or [])}.txt"
        p.write_text(out)
        return types.SimpleNamespace(returncode=None if timed_out else code, timed_out=timed_out, stdout=p)
    return run


BRANCH = {("rev-parse", "--symbolic-full-name", "main"): "refs/heads/main\n", ("remote",): "origin\n",
          ("rev-parse", "--abbrev-ref", "main@{upstream}"): "origin/main\n",
          ("rev-list", "--count", f"{SHA}..{NEW}"): "3\n", ("rev-list", "--count", f"{NEW}..{SHA}"): "0\n"}


class TestBranch:
    def test_online_gives_the_counts_and_asks_origin_once(self, fake, tmp_path):
        fake(BRANCH, present=(SHA, NEW))
        calls = []

        rec = workarea.freshness("/r", SHA, "main", runner(tmp_path, f"{NEW}\trefs/heads/main\n", calls=calls))

        assert calls == [["git", "ls-remote", "--exit-code", "origin", "refs/heads/main"]]
        assert (rec["ref_kind"], rec["compared_with"], rec["source"], rec["remote_sha"], rec["behind"], rec["ahead"]) == ("branch", "origin/main", "remote", NEW, 3, 0)
        assert rec["checked_at"] and rec["reason"] is None

    def test_head_on_an_attached_branch_uses_that_branch(self, fake, tmp_path):
        fake({**BRANCH, ("symbolic-ref", "--quiet", "HEAD"): "refs/heads/main\n", ("rev-parse", "--symbolic-full-name", "HEAD"): "HEAD\n"}, present=(SHA, NEW))

        rec = workarea.freshness("/r", SHA, "HEAD", runner(tmp_path, f"{NEW}\trefs/heads/main\n"))

        assert (rec["ref_kind"], rec["compared_with"], rec["behind"]) == ("branch", "origin/main", 3)

    def test_up_to_date(self, fake, tmp_path):
        fake({**BRANCH, ("rev-list", "--count", f"{SHA}..{SHA}"): "0\n"}, present=(SHA,))

        rec = workarea.freshness("/r", SHA, "main", runner(tmp_path, f"{SHA}\trefs/heads/main\n"))

        assert (rec["behind"], rec["ahead"]) == (0, 0)

    def test_ahead_only(self, fake, tmp_path):
        fake({**BRANCH, ("rev-list", "--count", f"{SHA}..{NEW}"): "0\n", ("rev-list", "--count", f"{NEW}..{SHA}"): "1\n"}, present=(SHA, NEW))

        rec = workarea.freshness("/r", SHA, "main", runner(tmp_path, f"{NEW}\trefs/heads/main\n"))

        assert (rec["behind"], rec["ahead"]) == (0, 1)

    def test_commits_not_fetched_give_no_counts_and_the_reason(self, fake, tmp_path):
        fake(BRANCH, present=(SHA,))

        rec = workarea.freshness("/r", SHA, "main", runner(tmp_path, f"{NEW}\trefs/heads/main\n"))

        assert (rec["behind"], rec["ahead"], rec["remote_sha"]) == (None, None, NEW) and rec["reason"] == "the newer commits have not been fetched"

    def test_no_upstream_falls_back_to_origin_branch_of_the_same_name(self, fake, tmp_path):
        answers = {k: v for k, v in BRANCH.items() if "--abbrev-ref" not in k} | {("show-ref", "--verify", "--quiet", "refs/remotes/origin/main"): "x"}
        fake(answers, present=(SHA, NEW))

        rec = workarea.freshness("/r", SHA, "main", runner(tmp_path, f"{NEW}\trefs/heads/main\n"))

        assert rec["compared_with"] == "origin/main" and rec["behind"] == 3

    def test_ls_remote_exit_2_means_the_ref_is_gone(self, fake, tmp_path):
        fake(BRANCH)

        rec = workarea.freshness("/r", SHA, "main", runner(tmp_path, "", code=2))

        assert rec["source"] == "remote" and rec["remote_sha"] is None and rec["reason"] == "the ref no longer exists on origin"

    def test_a_timeout_falls_back_to_the_tracking_branch(self, fake, tmp_path):
        fake({**BRANCH, ("rev-parse", "--verify", "--quiet", "refs/remotes/origin/main"): f"{NEW}\n"}, present=(SHA, NEW))

        rec = workarea.freshness("/r", SHA, "main", runner(tmp_path, timed_out=True))

        assert (rec["source"], rec["remote_sha"], rec["behind"]) == ("tracking", NEW, 3)

    def test_a_failed_ls_remote_with_no_tracking_branch_is_not_known(self, fake, tmp_path):
        fake(BRANCH)

        rec = workarea.freshness("/r", SHA, "main", runner(tmp_path, "", code=128))

        assert rec["source"] == "none" and rec["reason"] == "origin could not be reached and there is no remote-tracking branch."

    def test_no_remote_at_all(self, fake, tmp_path):
        fake({("rev-parse", "--symbolic-full-name", "main"): "refs/heads/main\n"})

        rec = workarea.freshness("/r", SHA, "main", runner(tmp_path))

        assert (rec["source"], rec["reason"]) == ("none", "The repository has no remote.")


class TestTagAndCommit:
    TAG = {("rev-parse", "--symbolic-full-name", "v1"): "refs/tags/v1\n", ("remote",): "origin\n"}

    def test_an_annotated_tag_uses_the_peeled_line(self, fake, tmp_path):
        fake(self.TAG | {("rev-list", "--count", f"{SHA}..{SHA}"): "0\n"})
        calls = []
        out = f"{'c' * 40}\trefs/tags/v1\n{SHA}\trefs/tags/v1^{{}}\n"

        rec = workarea.freshness("/r", SHA, "v1", runner(tmp_path, out, calls=calls))

        assert calls[0][-2:] == ["refs/tags/v1", "refs/tags/v1^{}"]
        assert (rec["ref_kind"], rec["compared_with"], rec["remote_sha"]) == ("tag", "tag v1", SHA)

    def test_a_moved_tag(self, fake, tmp_path):
        fake(self.TAG, present=(SHA,))

        rec = workarea.freshness("/r", SHA, "v1", runner(tmp_path, f"{NEW}\trefs/tags/v1\n"))

        assert rec["remote_sha"] == NEW and rec["source"] == "remote"

    def test_a_tag_cannot_fall_back_to_a_tracking_branch(self, fake, tmp_path):
        fake(self.TAG)

        rec = workarea.freshness("/r", SHA, "v1", runner(tmp_path, code=128))

        assert (rec["source"], rec["reason"]) == ("none", "origin could not be reached.")

    def test_a_commit_is_compared_with_the_default_branch(self, fake, tmp_path, monkeypatch):
        fake({("rev-parse", "--symbolic-full-name", SHA): "", ("remote",): "origin\n", ("rev-list", "--count", f"{SHA}..{NEW}"): "2\n",
              ("rev-list", "--count", f"{NEW}..{SHA}"): "0\n"}, present=(SHA, NEW))
        monkeypatch.setattr(workarea, "trusted", lambda top, sha: {"trusted": True, "why": "x", "default_branch": "origin/main"})

        rec = workarea.freshness("/r", SHA, SHA, runner(tmp_path, f"{NEW}\trefs/heads/main\n"))

        assert (rec["ref_kind"], rec["compared_with"], rec["behind"]) == ("commit", "origin/main", 2)


class TestTile:
    def rec(self, **kw):
        return {"ref_kind": "branch", "compared_with": "origin/main", "source": "remote", "remote_sha": NEW, "behind": 0, "ahead": 0,
                "checked_at": "2026-11-09 10:00", "reason": None} | kw

    def test_up_to_date(self):
        assert render.freshness_tile(self.rec(remote_sha=SHA)) == ("Freshness", "Up to date", "with origin/main, checked 2026-11-09 10:00 UTC")

    def test_up_to_date_from_the_last_fetch(self):
        assert render.freshness_tile(self.rec(remote_sha=SHA, source="tracking", checked_at="2026-11-01"))[2] == "with origin/main, as of the last fetch on 2026-11-01"
        assert render.freshness_tile(self.rec(remote_sha=SHA, source="tracking", checked_at=None))[2] == "with origin/main, as of the last fetch"

    def test_behind(self):
        assert render.freshness_tile(self.rec(behind=3)) == ("Freshness", "3 commits behind", f"origin/main is at {NEW[:7]}, checked 2026-11-09 10:00 UTC")
        assert render.freshness_tile(self.rec(behind=1))[1] == "1 commit behind"

    def test_ahead_only(self):
        assert render.freshness_tile(self.rec(ahead=2)) == ("Freshness", "Not on origin/main", "2 pinned commits are not on origin/main")
        assert render.freshness_tile(self.rec(ahead=1))[2] == "1 pinned commit is not on origin/main"

    def test_tag_unchanged_and_moved(self):
        tag = self.rec(ref_kind="tag", compared_with="tag v1", remote_sha=SHA)

        assert render.freshness_tile(tag) == ("Freshness", "Tag v1", "still points at this commit on origin")
        assert render.freshness_tile(tag | {"remote_sha": NEW, "behind": 2}) == ("Freshness", "Tag v1 moved", f"origin now has it at {NEW[:7]}")

    def test_a_moved_tag_whose_commit_was_not_fetched_is_moved_too(self):
        tag = self.rec(ref_kind="tag", compared_with="tag v1", behind=None, ahead=None)

        assert render.freshness_tile(tag)[1] == "Tag v1 moved"

    def test_not_known_shows_the_reason(self):
        got = render.freshness_tile(self.rec(source="none", remote_sha=None, behind=None, ahead=None, reason="The repository has no remote."))

        assert got == ("Freshness", "Not known", "The repository has no remote.")

    def test_counts_missing_shows_the_reason(self):
        got = render.freshness_tile(self.rec(behind=None, ahead=None, reason="the newer commits have not been fetched"))

        assert got[1] == "Not known" and "have not been fetched" in got[2]

    def test_no_record_gives_not_known(self):
        assert render.freshness_tile(None)[1:] == ("Not known", "This build did not record it.")


class TestStagePin:
    def build(self, tmp_path):
        import buildlog

        return buildlog.start(tmp_path / "out", repo="r", sha=SHA, ref="main", version="test", options={})

    def pin_details(self, build):
        import buildlog

        return buildlog.latest(buildlog.load(build), "pin")["details"]

    def test_the_pin_record_holds_the_freshness(self, tmp_path, monkeypatch):
        import stages

        rec = {"ref_kind": "branch", "compared_with": "origin/main", "source": "remote", "remote_sha": NEW, "behind": 3, "ahead": 0,
               "checked_at": "2026-11-09 10:00", "reason": None}
        monkeypatch.setattr(workarea, "trusted", lambda top, sha: {"trusted": True, "why": "x", "default_branch": None})
        monkeypatch.setattr(workarea, "freshness", lambda top, sha, ref, run, timeout=15: rec)
        build = self.build(tmp_path)

        stages.stage_pin(build, str(tmp_path), "main", SHA, tmp_path / "area")

        assert self.pin_details(build)["freshness"] == rec

    def test_a_failure_in_freshness_never_stops_prepare(self, tmp_path, monkeypatch):
        import stages

        def boom(*a, **k):
            raise RuntimeError("git went away")

        monkeypatch.setattr(workarea, "trusted", lambda top, sha: {"trusted": True, "why": "x", "default_branch": None})
        monkeypatch.setattr(workarea, "freshness", boom)
        build = self.build(tmp_path)

        out = stages.stage_pin(build, str(tmp_path), "main", SHA, tmp_path / "area")

        fresh = self.pin_details(build)["freshness"]
        assert out["sha"] == SHA and fresh["source"] == "none" and "git went away" in fresh["reason"]
