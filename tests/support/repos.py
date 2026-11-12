"""Builders for the git repositories tests run against: the fixture copies, a fake repo reader and small helpers."""
import os
import re
import shutil
import subprocess
import types
from pathlib import Path

from paths import FIXTURES

PYFIX = FIXTURES / "pyrepo"
JSFIX = FIXTURES / "jsrepo"
CSFIX = FIXTURES / "csrepo"
PYLIB = FIXTURES / "pylib"
CSCAKE = FIXTURES / "cscake"
PYFASTAPI = FIXTURES / "pyfastapi"


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


def line_of(root, rel, name):
    """The 1-based line of `rel` under `root` that holds the marker `@<name>`; raises when absent or repeated."""
    pattern = re.compile(r"@" + re.escape(name) + r"(?![\w-])")
    lines = [i for i, text in enumerate((Path(root) / rel).read_text(encoding="utf-8").splitlines(), 1) if pattern.search(text)]
    if len(lines) != 1:
        raise LookupError(f"marker @{name} found {len(lines)} times in {rel}")
    return lines[0]


def key_line(root, rel, key):
    """The 1-based line of `rel` under `root` whose text holds `"<key>"` first; for JSON files, which cannot hold markers."""
    for i, text in enumerate((Path(root) / rel).read_text(encoding="utf-8").splitlines(), 1):
        if f'"{key}"' in text:
            return i
    raise LookupError(f'key "{key}" not found in {rel}')


def _commit_fixture(src: Path, dest: Path, name: str, chmod=()):
    repo = Path(dest) / name
    shutil.copytree(src, repo, ignore=shutil.ignore_patterns("__pycache__", "node_modules"))
    for rel in chmod:
        (repo / rel).chmod(0o755)
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
           "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@x.io", "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@x.io"}

    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env).stdout.strip()

    git("init", "-b", "main")
    git("add", "-A")
    git("commit", "-m", "fixture")
    return types.SimpleNamespace(path=str(repo), sha=git("rev-parse", "HEAD"),
                                 line_of=lambda rel, marker: line_of(repo, rel, marker),
                                 key_line=lambda rel, key: key_line(repo, rel, key))


def build_py_repo(dest: Path):
    """Copy the Python fixture repository (tests/fixtures/pyrepo) to `dest` and commit it once on main."""
    return _commit_fixture(PYFIX, dest, "pyrepo", chmod=[Path("scripts") / "seed.sh"])


def build_js_repo(dest: Path):
    """Copy the JavaScript fixture repository (tests/fixtures/jsrepo) to `dest` and commit it once on main."""
    return _commit_fixture(JSFIX, dest, "jsrepo")


def build_cs_repo(dest: Path):
    """Copy the C# fixture repository (tests/fixtures/csrepo) to `dest` and commit it once on main."""
    return _commit_fixture(CSFIX, dest, "csrepo")


def build_fastapi_repo(dest: Path):
    """Copy the FastAPI fixture (tests/fixtures/pyfastapi: two routes with a dependency each, and one with a lambda) to `dest` and commit it once on main."""
    return _commit_fixture(PYFASTAPI, dest, "pyfastapi")


def build_cake_repo(dest: Path):
    """Copy the Cake fixture (tests/fixtures/cscake: a `build.cake` with four tasks and a one-file program) to `dest` and commit it once on main."""
    return _commit_fixture(CSCAKE, dest, "cscake")


def build_pylib_repo(dest: Path):
    """Copy the Python library fixture (tests/fixtures/pylib) to `dest` and commit it once on main."""
    return _commit_fixture(PYLIB, dest, "pylib")


def build_mixed_pysub_repo(dest: Path):
    """PYFIX under `backend/` and the JS fixture's web package under `frontend/`, committed once on main as `mixedsub`."""
    parts = Path(dest) / "parts"
    shutil.copytree(PYFIX, parts / "backend", ignore=shutil.ignore_patterns("__pycache__", "node_modules"))
    shutil.copytree(JSFIX / "packages" / "web", parts / "frontend", ignore=shutil.ignore_patterns("node_modules"))
    (parts / "backend" / "scripts" / "seed.sh").chmod(0o755)
    return _commit_fixture(parts, dest, "mixedsub")


def make_repo(tmp_path, source):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text(source)
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull, "GIT_AUTHOR_NAME": "A", "GIT_AUTHOR_EMAIL": "a@x.io",
           "GIT_COMMITTER_NAME": "A", "GIT_COMMITTER_EMAIL": "a@x.io"}
    for args in (["init", "-b", "main"], ["add", "-A"], ["commit", "-m", "x"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)
    return repo
