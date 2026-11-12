"""The launcher scripts/dossier.py and dossier.resources: how the package is found and run (plan 014, D1 and D7)."""
import importlib.util
import re
import shutil
import tomllib
from pathlib import Path

import pytest

from dossier import resources
from paths import SKILL_ROOT

LAUNCHER = SKILL_ROOT / "scripts" / "dossier.py"
HEADER = re.compile(r"^# /// script\n(?P<body>(?:#.*\n)*?)# ///$", re.M)


def pep723(path: Path) -> dict:
    body = HEADER.search(path.read_text())["body"]
    return tomllib.loads("".join(line[2:] + "\n" for line in body.splitlines()))


def load_copy(dest: Path):
    """resources.py copied to `dest` and imported from there, so its __file__ points into `dest`."""
    dest.parent.mkdir(parents=True)
    shutil.copy(Path(resources.__file__), dest)
    spec = importlib.util.spec_from_file_location("resources_copy", dest)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestLauncherHeader:
    def test_dependencies_match_the_project(self):
        project = tomllib.loads((SKILL_ROOT / "pyproject.toml").read_text())["project"]

        header = pep723(LAUNCHER)

        assert header["dependencies"] == project["dependencies"]

    def test_python_floor_matches_the_project(self):
        project = tomllib.loads((SKILL_ROOT / "pyproject.toml").read_text())["project"]

        header = pep723(LAUNCHER)

        assert header["requires-python"] == project["requires-python"]


class TestData:
    def test_points_inside_the_package_data_folder(self):
        root = resources.data()

        assert isinstance(root, Path)
        assert root == SKILL_ROOT / "src" / "dossier" / "data"

    def test_joins_its_parts(self):
        assert resources.data("schemas", "cards") == SKILL_ROOT / "src" / "dossier" / "data" / "schemas" / "cards"

    def test_data_not_on_disk_raises(self, monkeypatch):
        class NotAPath:
            def joinpath(self, *parts):
                return self

        monkeypatch.setattr(resources, "files", lambda package: NotAPath())

        with pytest.raises(RuntimeError, match="package data is not on disk"):
            resources.data()


class TestSkillRoot:
    def test_holds_skill_md_and_version(self):
        root = resources.skill_root()

        assert root == SKILL_ROOT
        assert (root / "SKILL.md").is_file() and (root / "VERSION").is_file()

    def test_missing_skill_md_raises_with_the_folder(self, tmp_path):
        copy = load_copy(tmp_path / "src" / "dossier" / "resources.py")

        with pytest.raises(RuntimeError, match=f"no SKILL.md in {re.escape(str(tmp_path))}"):
            copy.skill_root()


class TestVersion:
    def test_equals_the_version_file(self):
        assert resources.version() == (SKILL_ROOT / "VERSION").read_text().strip()

    def test_strips_the_newline(self, tmp_path):
        (tmp_path / "SKILL.md").write_text("")
        (tmp_path / "VERSION").write_text("9.8.7\n")
        copy = load_copy(tmp_path / "src" / "dossier" / "resources.py")

        assert copy.version() == "9.8.7"
