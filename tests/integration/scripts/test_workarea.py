import json
import subprocess
from pathlib import Path

import pytest

import workarea


def head(path):
    return subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def status(path):
    return subprocess.run(["git", "-C", str(path), "status", "--porcelain"], capture_output=True, text=True).stdout


@pytest.fixture
def area(tmp_path, hygiene_repo):
    return workarea.area_for("hygiene", hygiene_repo.path, "root1", tmp_path / "cache")


class TestEnsureCheckout:
    def test_creates_a_verified_copy_and_leaves_the_source_alone(self, area, hygiene_repo):
        before = status(hygiene_repo.path)

        res = workarea.ensure_checkout(area, hygiene_repo.path, hygiene_repo.main_sha)

        assert (res["created"], res["verified"], head(res["path"])) == (True, True, hygiene_repo.main_sha)
        assert status(hygiene_repo.path) == before

    def test_second_call_reuses_and_moves(self, area, hygiene_repo):
        workarea.ensure_checkout(area, hygiene_repo.path, hygiene_repo.main_sha)

        res = workarea.ensure_checkout(area, hygiene_repo.path, hygiene_repo.feature_sha)

        assert (res["created"], head(res["path"])) == (False, hygiene_repo.feature_sha)

    def test_untracked_files_are_removed(self, area, hygiene_repo):
        res = workarea.ensure_checkout(area, hygiene_repo.path, hygiene_repo.main_sha)
        (area / "checkout" / "junk.txt").write_text("x")

        workarea.ensure_checkout(area, hygiene_repo.path, hygiene_repo.main_sha)

        assert not (area / "checkout" / "junk.txt").exists()

    def test_commit_added_after_first_clone_is_found(self, area, hygiene_repo):
        workarea.ensure_checkout(area, hygiene_repo.path, hygiene_repo.main_sha)
        subprocess.run(["git", "-C", hygiene_repo.path, "-c", "user.name=t", "-c", "user.email=t@x", "commit", "--allow-empty", "-m", "later"],
                       check=True, capture_output=True)
        new = head(hygiene_repo.path)

        res = workarea.ensure_checkout(area, hygiene_repo.path, new)

        assert head(res["path"]) == new


class TestTrusted:
    def test_tag(self, hygiene_repo):
        assert workarea.trusted(hygiene_repo.path, hygiene_repo.tag_sha)["why"] == "tag v1.0"

    def test_tip_of_default_branch(self, hygiene_repo):
        r = workarea.trusted(hygiene_repo.path, hygiene_repo.main_sha)

        assert (r["trusted"], r["why"]) == (True, "tip of the default branch main")

    def test_reachable_from_default_branch(self, hygiene_repo):
        r = workarea.trusted(hygiene_repo.path, hygiene_repo.middle_sha)

        assert (r["trusted"], r["why"]) == (True, "reachable from the default branch main")

    def test_feature_branch_is_untrusted(self, hygiene_repo):
        r = workarea.trusted(hygiene_repo.path, hygiene_repo.feature_sha)

        assert (r["trusted"], r["why"]) == (False, "not a tag and not on the default branch main")

    def test_clone_uses_origin_head(self, tmp_path, hygiene_repo):
        dest = tmp_path / "clone"
        subprocess.run(["git", "clone", "-q", hygiene_repo.path, str(dest)], check=True)

        r = workarea.trusted(str(dest), hygiene_repo.main_sha)

        assert r["default_branch"] == "origin/main"


class TestAreaFor:
    def test_other_owner_raises(self, tmp_path):
        workarea.area_for("x", "/one", "r1", tmp_path)

        with pytest.raises(workarea.CheckoutError):
            workarea.area_for("x", "/two", "r2", tmp_path)

    def test_writes_owner_file(self, tmp_path):
        a = workarea.area_for("x", "/one", "r1", tmp_path)

        assert json.loads((a / "owner.json").read_text()) == {"repo": "/one", "root_commit": "r1"}


class TestClean:
    def test_refuses_path_outside_cache_root(self, tmp_path):
        other = tmp_path / "elsewhere" / "x"
        other.mkdir(parents=True)

        with pytest.raises(workarea.CheckoutError):
            workarea.clean(other, tmp_path / "cache")

    def test_refuses_shared_tools_folder(self, tmp_path):
        (tmp_path / ".dossier-tools").mkdir()

        with pytest.raises(workarea.CheckoutError):
            workarea.clean(tmp_path / ".dossier-tools", tmp_path)

    def test_removes_a_real_area(self, tmp_path):
        a = workarea.area_for("x", "/one", "r1", tmp_path)

        assert workarea.clean(a, tmp_path) is True and not a.exists()


class TestFreshness:
    """Real git: a bare remote three commits ahead of a clone that is pinned at an older commit (D6)."""

    ENV = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@x.io",
           "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@x.io"}

    @staticmethod
    def git(cwd, *args):
        import os

        r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, env={**os.environ, **TestFreshness.ENV})
        assert r.returncode == 0, r.stderr
        return r.stdout.strip()

    @pytest.fixture
    def repos(self, tmp_path):
        bare, work, clone = tmp_path / "remote.git", tmp_path / "work", tmp_path / "clone"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
        subprocess.run(["git", "clone", "-q", str(bare), str(work)], check=True, capture_output=True)
        for i in range(4):
            (work / "f.txt").write_text(f"{i}\n")
            self.git(work, "add", "-A")
            self.git(work, "commit", "-qm", f"c{i}")
            if i == 0:
                self.git(work, "push", "-q", "origin", "HEAD:main")
                subprocess.run(["git", "clone", "-q", str(bare), str(clone)], check=True, capture_output=True)
        self.git(work, "push", "-q", "origin", "HEAD:main")
        self.git(clone, "fetch", "-q", "origin")
        return bare, clone, self.git(clone, "rev-parse", "HEAD")

    @staticmethod
    def runner(tmp_path, cwd):
        import functools

        import sandbox

        return functools.partial(sandbox.run, area=tmp_path / "area", cwd=Path(cwd), profile="restricted")

    def test_online_the_clone_is_three_behind(self, repos, tmp_path):
        _, clone, pin = repos

        rec = workarea.freshness(str(clone), pin, "main", self.runner(tmp_path, clone))

        assert (rec["source"], rec["behind"], rec["ahead"], rec["compared_with"]) == ("remote", 3, 0, "origin/main")

    def test_a_remote_that_cannot_be_reached_falls_back_to_the_last_fetch(self, repos, tmp_path):
        bare, clone, pin = repos
        self.git(clone, "remote", "set-url", "origin", str(tmp_path / "missing.git"))

        rec = workarea.freshness(str(clone), pin, "main", self.runner(tmp_path, clone))

        assert (rec["source"], rec["behind"]) == ("tracking", 3) and rec["checked_at"]

    def test_a_commit_made_only_in_the_clone_is_ahead(self, repos, tmp_path):
        _, clone, _ = repos
        (clone / "g.txt").write_text("x\n")
        self.git(clone, "add", "-A")
        self.git(clone, "commit", "-qm", "local")
        pin = self.git(clone, "rev-parse", "HEAD")

        rec = workarea.freshness(str(clone), pin, "main", self.runner(tmp_path, clone))

        assert (rec["ahead"], rec["behind"]) == (1, 3)

    def test_a_pinned_commit_with_no_ref_is_compared_with_the_default_branch(self, repos, tmp_path):
        _, clone, pin = repos

        rec = workarea.freshness(str(clone), pin, pin, self.runner(tmp_path, clone))

        assert (rec["ref_kind"], rec["compared_with"], rec["behind"]) == ("commit", "origin/main", 3)

    def test_the_repository_is_not_written(self, repos, tmp_path):
        _, clone, pin = repos
        before = status(clone)

        workarea.freshness(str(clone), pin, "main", self.runner(tmp_path, clone))

        assert status(clone) == before and self.git(clone, "rev-parse", "HEAD") == pin
