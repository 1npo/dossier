import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import render  # noqa: E402

SHA = "a" * 40


class FakeRepo:
    """Stands in for gather.Repo: serves blobs from a dict and records which paths were read."""

    def __init__(self, blobs, dirs=()):
        self.blobs, self.dirs, self.reads = blobs, set(dirs), []

    def read(self, spec):
        path = spec.split(":", 1)[1]
        self.reads.append(path)
        if path in self.blobs:
            return "blob", self.blobs[path]
        return ("tree", b"") if path.rstrip("/") in self.dirs else None


@pytest.fixture
def make_cites():
    def build(blobs, dirs=(), secret_signals=None):
        facts = {"repo": {"sha": SHA, "path": "/repo", "remote": None}}
        if secret_signals:
            facts["secret_signals"] = secret_signals
        cites = render.Cites(facts)
        cites.repo = FakeRepo(blobs, dirs)
        return cites
    return build


@pytest.fixture
def git_repo(tmp_path):
    """A small real repository: a departed author, a current author, a bot, and a file that was renamed. HEAD is dated 2026-06-01."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args, who=None, day=None):
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
        if who:
            name, email = who
            env.update(GIT_AUTHOR_NAME=name, GIT_AUTHOR_EMAIL=email, GIT_COMMITTER_NAME=name, GIT_COMMITTER_EMAIL=email,
                       GIT_AUTHOR_DATE=f"{day}T12:00:00+00:00", GIT_COMMITTER_DATE=f"{day}T12:00:00+00:00")
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)

    def commit(who, day, message, **files):
        for path, text in files.items():
            target = repo / path.replace("__", "/")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        git("add", "-A")
        git("commit", "-m", message, who=who, day=day)

    dana, ann, bot = ("Dana Cole", "dana@x.io"), ("Ann Lee", "ann@x.io"), ("dependabot[bot]", "bot@x.io")
    git("init", "-b", "main")
    commit(dana, "2025-01-10", "legacy", old__legacy_py="a = 1\nb = 2\nc = 3\n", shared_py="x\ny\nz\n")
    commit(ann, "2025-02-01", "app", src__app_py="1\n2\n3\n4\n", shared_py="x\ny\nz\nw\n")
    commit(bot, "2025-03-01", "bump", deps_txt="a\nb\n")
    (repo / "src" / "app_py").rename(repo / "src" / "main_py")
    commit(ann, "2026-03-01", "rename", **{})
    commit(ann, "2026-06-01", "edit", src__main_py="1\n2\n3\n4\n5\n")
    return repo
