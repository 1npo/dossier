import os
import re
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import render  # noqa: E402

SHA = "a" * 40
collect_ignore_glob = ["fixtures/*"]
PYFIX = Path(__file__).resolve().parent / "fixtures" / "pyrepo"


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


INSTALL_SH = """#!/bin/sh
# install.sh: writes out what a restore can see
mkdir -p "$HOME/report"
env | cut -d= -f1 | sort > "$HOME/report/env-names.txt"
printf '%s\\n' "$HOME" > "$HOME/report/home.txt"
pwd > "$HOME/report/cwd.txt"
for v in UV_CACHE_DIR npm_config_cache NUGET_PACKAGES DOTNET_CLI_HOME PIP_CACHE_DIR; do
  eval d=\\$$v
  mkdir -p "$d" && : > "$d/written-by-install" && echo "$d/written-by-install" >> "$HOME/report/cache-markers.txt"
done
"""

SLEEPER_SH = """#!/bin/sh
# sleeper.sh: starts a background child and never finishes on its own
sleep 300 &
echo $! > "$HOME/child.pid"
echo $$ > "$HOME/parent.pid"
wait
"""


@pytest.fixture
def hygiene_repo(tmp_path):
    """A repository with a tag, a default branch with two later commits, and a side branch.

    tag_sha: commit 1 (tagged v1.0). middle_sha: commit 2 on main. main_sha: commit 3 (tip of main).
    feature_sha: commit 4 on feature/x, not on main.
    """
    import types

    repo = tmp_path / "hygiene"
    repo.mkdir()
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
           "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@x.io", "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@x.io"}

    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env).stdout.strip()

    def commit(message, **files):
        for path, text in files.items():
            f = repo / path
            f.write_text(text)
            if path.endswith(".sh"):
                f.chmod(0o755)
        git("add", "-A")
        git("commit", "-m", message)
        return git("rev-parse", "HEAD")

    git("init", "-b", "main")
    tag_sha = commit("one", **{"install.sh": INSTALL_SH, "sleeper.sh": SLEEPER_SH, "app.py": 'print("hi")\n', "uv.lock": "version = 1\n"})
    git("tag", "v1.0")
    middle_sha = commit("two", **{"app.py": 'print("two")\n'})
    main_sha = commit("three", **{"app.py": 'print("three")\n'})
    git("checkout", "-b", "feature/x")
    feature_sha = commit("four", **{"feature.py": "x = 1\n"})
    git("checkout", "main")
    return types.SimpleNamespace(path=str(repo), tag_sha=tag_sha, middle_sha=middle_sha, main_sha=main_sha, feature_sha=feature_sha)


def line_of(root, rel, name):
    """The 1-based line of `rel` under `root` that holds the marker `@<name>`; raises when absent or repeated."""
    pattern = re.compile(r"@" + re.escape(name) + r"(?![\w-])")
    lines = [i for i, text in enumerate((Path(root) / rel).read_text(encoding="utf-8").splitlines(), 1) if pattern.search(text)]
    if len(lines) != 1:
        raise LookupError(f"marker @{name} found {len(lines)} times in {rel}")
    return lines[0]


@pytest.fixture(name="line_of")
def line_of_fixture():
    return line_of


@pytest.fixture
def py_repo(tmp_path):
    """The Python fixture repository (tests/fixtures/pyrepo) as a git repository with one commit on main."""
    repo = tmp_path / "pyrepo"
    shutil.copytree(PYFIX, repo, ignore=shutil.ignore_patterns("__pycache__"))
    (repo / "scripts" / "seed.sh").chmod(0o755)
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
           "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@x.io", "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@x.io"}

    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env).stdout.strip()

    git("init", "-b", "main")
    git("add", "-A")
    git("commit", "-m", "fixture")
    return types.SimpleNamespace(path=str(repo), sha=git("rev-parse", "HEAD"),
                                 line_of=lambda rel, name: line_of(repo, rel, name))
