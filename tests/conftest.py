import os
import subprocess
import types

import pytest

from dossier.render import page as render
from repos import (INSTALL_SH, SLEEPER_SH, FakeRepo, build_cake_repo, build_cs_repo, build_fastapi_repo, build_js_repo,
                   build_mixed_pysub_repo, build_py_repo, build_pylib_repo, line_of)

os.environ["DOSSIER_OFFLINE"] = "1"  # no test reaches the network for reference data
SHA = "a" * 40
collect_ignore_glob = ["fixtures/*"]


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


@pytest.fixture
def history_repo(tmp_path):
    """Two humans, an agent, a bot, a rename, three files that change together, a merge, a tag, a remote ref, a HACK marker
    and a human commit that credits Claude as co-author. HEAD is dated 2026-06-01."""
    repo = tmp_path / "hrepo"
    repo.mkdir()

    def git(*args, who=None, day=None):
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
        if who:
            name, email = who
            env.update(GIT_AUTHOR_NAME=name, GIT_AUTHOR_EMAIL=email, GIT_COMMITTER_NAME=name, GIT_COMMITTER_EMAIL=email,
                       GIT_AUTHOR_DATE=f"{day}T12:00:00+00:00", GIT_COMMITTER_DATE=f"{day}T12:00:00+00:00")
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env, text=True).stdout

    def commit(who, day, message, files=None):
        for path, text in (files or {}).items():
            target = repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        git("add", "-A")
        git("commit", "-m", message, who=who, day=day)

    ann, bob = ("Ann Lee", "ann@x.io"), ("Bob Ray", "bob@x.io")
    claude, bot = ("Claude", "noreply@anthropic.com"), ("dependabot[bot]", "bot@x.io")
    git("init", "-b", "main")
    for i, day in enumerate(("2025-01-10", "2025-02-10", "2025-03-10"), 1):
        body = "\n\n" + "\n".join(f"detail {n}" for n in range(8)) if i == 1 else ""
        commit(ann, day, f"feat: step {i}{body}", {"src/a.py": "a\n" * i, "src/b.py": "b\n" * i, "src/c.py": "c\n" * i})
    commit(bob, "2025-04-01", "fix: lone change", {"src/d.py": "d = 1\n"})
    commit(claude, "2025-05-01", "feat: agent work", {"src/e.py": "e = 1\n"})
    commit(bot, "2025-06-01", "chore: bump", {"deps.txt": "a\nb\n"})
    (repo / "src" / "d.py").rename(repo / "src" / "d2.py")
    commit(bob, "2025-07-01", "refactor: rename")
    git("tag", "v1.0", who=bob, day="2025-07-02")
    git("switch", "-c", "feat/x")
    commit(ann, "2025-08-01", "feat: on a branch", {"src/x.py": "x = 1  # HACK: temporary\n"})
    git("switch", "main")
    commit(bob, "2025-09-01", "docs: on main", {"README.md": "hello\n"})
    git("merge", "--no-ff", "feat/x", "-m", "Merge branch 'feat/x'", who=bob, day="2026-01-01")
    commit(bob, "2026-05-01", "feat: with an assistant\n\nCo-authored-by: Claude <noreply@anthropic.com>", {"src/a.py": "a\n" * 5})
    sha = git("rev-parse", "HEAD").strip()
    git("update-ref", "refs/remotes/origin/feat-y", sha)
    commit(ann, "2026-06-01", "fix: latest", {"src/b.py": "b\n" * 6})
    return repo


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


@pytest.fixture(name="line_of")
def line_of_fixture():
    return line_of


@pytest.fixture
def py_repo(tmp_path):
    """The Python fixture repository as a git repository with one commit on main."""
    return build_py_repo(tmp_path)


@pytest.fixture
def fastapi_repo(tmp_path):
    """The FastAPI fixture repository as a git repository with one commit on main."""
    return build_fastapi_repo(tmp_path)


@pytest.fixture
def js_repo(tmp_path):
    """The JavaScript fixture repository as a git repository with one commit on main."""
    return build_js_repo(tmp_path)


@pytest.fixture
def cake_repo(tmp_path):
    """The Cake fixture repository as a git repository with one commit on main."""
    return build_cake_repo(tmp_path)


@pytest.fixture
def cs_repo(tmp_path):
    """The C# fixture repository as a git repository with one commit on main."""
    return build_cs_repo(tmp_path)
