import re
import subprocess
from pathlib import Path

import pytest

from conftest import PYFIX, line_of

MARKERS = """ep-script ep-main-module ep-guard ep-route ep-route2 ep-docker ep-make ep-cron ep-shebang
io-cli io-print io-exit io-log-get io-log io-env io-db-connect io-file-write io-file-read io-outbound
import-up state-module state-registry fail-catchall dead-func cycle-a cycle-b
model-item model-status model-order field-items model-sql
bs-import bs-getattr bs-registry bs-fixture cc-lock cc-thread cc-async
test-1 test-skip test-mock ci-pytest""".split()


def all_files():
    return [p for p in PYFIX.rglob("*") if p.is_file() and "__pycache__" not in p.parts]


class TestPyFixture:
    @pytest.mark.parametrize("name", MARKERS)
    def test_marker_appears_exactly_once_in_the_fixture(self, name):
        pattern = re.compile(r"@" + re.escape(name) + r"(?![\w-])")

        hits = [p for p in all_files() if pattern.search(p.read_text(encoding="utf-8"))]
        count = sum(len(pattern.findall(p.read_text(encoding="utf-8"))) for p in hits)

        assert count == 1

    def test_every_python_file_compiles(self):
        for path in all_files():
            if path.suffix == ".py":
                compile(path.read_text(encoding="utf-8"), str(path), "exec")

    def test_seed_script_has_marker_on_line_two(self):
        assert line_of(PYFIX, "scripts/seed.sh", "ep-shebang") == 2


class TestLineOf:
    def test_missing_marker_raises(self):
        with pytest.raises(LookupError):
            line_of(PYFIX, "README.md", "nope")

    def test_prefix_marker_does_not_match_a_longer_one(self):
        assert line_of(PYFIX, "src/shopcart/api.py", "ep-route") != line_of(PYFIX, "src/shopcart/api.py", "ep-route2")


class TestPyRepoFixture:
    def test_repo_is_committed_with_executable_seed_script(self, py_repo):
        out = subprocess.run(["git", "-C", py_repo.path, "ls-tree", "-r", py_repo.sha, "scripts/seed.sh"],
                             capture_output=True, text=True).stdout

        assert out.startswith("100755")
        assert Path(py_repo.path, "Makefile").read_text().startswith("test:")
