import re

import pytest

from conftest import PYLIB, build_pylib_repo

MARKERS = "api-reexport api-parse api-config api-fast".split()


def all_files():
    return [p for p in PYLIB.rglob("*") if p.is_file() and "__pycache__" not in p.parts]


class TestPyLibFixture:
    @pytest.mark.parametrize("name", MARKERS)
    def test_marker_appears_exactly_once_in_the_fixture(self, name):
        pattern = re.compile(r"@" + re.escape(name) + r"(?![\w-])")

        count = sum(len(pattern.findall(p.read_text(encoding="utf-8"))) for p in all_files())

        assert count == 1

    def test_every_file_is_under_forty_lines(self):
        long = [str(p.relative_to(PYLIB)) for p in all_files() if len(p.read_text().splitlines()) >= 40]

        assert long == []

    def test_the_four_projects_are_present(self):
        names = sorted(p.name for p in PYLIB.iterdir() if p.is_dir())

        assert names == ["app", "badlib", "flatlib", "typedlib"]

    def test_only_typedlib_has_a_py_typed_marker(self):
        found = sorted(p.relative_to(PYLIB).parts[0] for p in PYLIB.rglob("py.typed"))

        assert found == ["typedlib"]

    def test_build_pylib_repo_commits_the_fixture(self, tmp_path):
        repo = build_pylib_repo(tmp_path)

        assert len(repo.sha) == 40
