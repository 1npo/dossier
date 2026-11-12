"""Unit tests for tools/move_modules.py: each import form it rewrites, what it leaves alone, dry run and --check."""
import os
import subprocess
import sys
from pathlib import Path

import pytest


import move_modules as mm  # noqa: E402

MOVES = mm.parse_map("""
# a comment line
render render.page      # renamed leaf
py_api adapters.python.api
config core.config
dossier cli.app
""")


def rw(text: str) -> str:
    return mm.rewrite(text, MOVES)[0]


def git(repo: Path, *args: str) -> str:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull, "GIT_AUTHOR_NAME": "T",
           "GIT_AUTHOR_EMAIL": "t@x.io", "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@x.io"}
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A tiny skill: scripts/render.py, a test that imports it, a fixture file that must not change."""
    files = {
        "scripts/render.py": "X = 1\n",
        "scripts/main.py": "import render  # noqa: E402\n",
        "tests/unit/test_x.py": "import render\n\ndef test():\n    import render as r\n    assert r.X\n",
        "tests/fixtures/repo/app.py": "import render\n",
        "notes.txt": "import render\n",
        ".gitignore": "a.map\n",
    }
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "init")
    (tmp_path / "a.map").write_text("render render.page\n")
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestParseMap:
    def test_comments_and_blank_lines_are_ignored(self):
        assert set(MOVES) == {"render", "py_api", "config", "dossier"}
        assert MOVES["render"] == mm.Move("render", "render.page")

    def test_bad_line_raises(self):
        with pytest.raises(mm.MoveError, match="line 1"):
            mm.parse_map("render\n")

    def test_dotted_old_name_raises(self):
        with pytest.raises(mm.MoveError):
            mm.parse_map("a.b render.page\n")

    def test_name_mapped_twice_raises(self):
        with pytest.raises(mm.MoveError, match="twice"):
            mm.parse_map("a x.a\na y.a\n")


class TestMove:
    def test_paths_and_names(self):
        m = MOVES["py_api"]

        assert (m.parent, m.leaf, m.full) == ("dossier.adapters.python", "api", "dossier.adapters.python.api")
        assert m.source == Path("scripts/py_api.py")
        assert m.dest == Path("src/dossier/adapters/python/api.py")


class TestRewriteImport:
    def test_same_leaf_drops_the_alias(self):
        assert rw("import config\n") == "from dossier.core import config\n"

    def test_different_leaf_binds_the_old_name(self):
        assert rw("import render\n") == "from dossier.render import page as render\n"
        assert rw("import dossier\n") == "from dossier.cli import app as dossier\n"

    def test_alias_is_kept(self):
        assert rw("import py_api as api\n") == "from dossier.adapters.python import api\n"
        assert rw("import render as r\n") == "from dossier.render import page as r\n"

    def test_unmapped_import_is_unchanged(self):
        text = "import os\nimport json as j\n"

        assert rw(text) == text


class TestRewriteMultiNameImport:
    def test_each_name_gets_its_own_line(self):
        assert rw("import os, render, sys\n") == "import os\nfrom dossier.render import page as render\nimport sys\n"

    def test_indentation_is_kept_on_every_line(self):
        out = rw("def f():\n    import json, config\n    return config\n")

        assert out == "def f():\n    import json\n    from dossier.core import config\n    return config\n"

    def test_statement_sharing_a_line_is_joined_with_semicolons(self):
        assert rw("x = 1; import os, config\n") == "x = 1; import os; from dossier.core import config\n"


class TestRewriteNested:
    def test_function_level_import_keeps_its_indentation(self):
        out = rw("def f():\n    if True:\n        import render\n    return render\n")

        assert out == "def f():\n    if True:\n        from dossier.render import page as render\n    return render\n"


class TestRewriteFrom:
    def test_only_the_module_token_changes(self):
        assert rw("from render import E, badge\n") == "from dossier.render.page import E, badge\n"

    def test_multi_line_from_import_keeps_parentheses_and_breaks(self):
        text = "from render import (\n    E,\n    badge,  # used twice\n)\n"

        assert rw(text) == "from dossier.render.page import (\n    E,\n    badge,  # used twice\n)\n"

    def test_relative_import_is_unchanged(self):
        assert rw("from .render import E\n") == "from .render import E\n"

    def test_module_that_only_starts_with_an_old_name_is_unchanged(self):
        assert rw("from render_util import x\nimport renderer\n") == "from render_util import x\nimport renderer\n"


class TestRewriteComments:
    def test_trailing_comment_is_kept(self):
        assert rw("import render  # noqa: E402\n") == "from dossier.render import page as render  # noqa: E402\n"

    def test_trailing_comment_is_repeated_on_every_split_line(self):
        out = rw("import os, render  # noqa: E402\n")

        assert out == "import os  # noqa: E402\nfrom dossier.render import page as render  # noqa: E402\n"


class TestRewriteLeavesCodeAlone:
    def test_strings_and_attributes_are_unchanged(self):
        text = 's = "import render"\nt = """\nimport config\n"""\nx = render.page\ny = mod.config.load()\n'

        assert rw(text) == text

    def test_the_edit_list_names_each_statement(self):
        _, edits = mm.rewrite("import os\nimport render\n", MOVES)

        assert edits == [(2, "import render", "from dossier.render import page as render")]


class TestRewritePackageImport:
    def test_from_package_import_of_an_existing_submodule_is_left(self, tmp_path, monkeypatch):
        (tmp_path / "src" / "dossier").mkdir(parents=True)
        (tmp_path / "src" / "dossier" / "resources.py").write_text("")
        monkeypatch.chdir(tmp_path)

        assert rw("from dossier import resources\n") == "from dossier import resources\n"

    def test_from_flat_cli_import_is_rewritten(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        assert rw("from dossier import cmd_check\n") == "from dossier.cli.app import cmd_check\n"


class TestRun:
    def test_moves_the_file_rewrites_imports_and_creates_init_files(self, repo):
        code = mm.main(["a.map"])

        assert code == 0
        assert not (repo / "scripts/render.py").exists()
        assert (repo / "src/dossier/render/page.py").read_text() == "X = 1\n"
        assert (repo / "scripts/main.py").read_text() == "from dossier.render import page as render  # noqa: E402\n"
        assert "    from dossier.render import page as r\n" in (repo / "tests/unit/test_x.py").read_text()
        init = (repo / "src/dossier/render/__init__.py").read_text()
        assert init.startswith('"""The page: citations') and "__all__: list[str] = []" in init
        assert (repo / "src/dossier/__init__.py").is_file()
        status = git(repo, "status", "--porcelain")
        assert "R  scripts/render.py -> src/dossier/render/page.py" in status
        assert "A  src/dossier/render/__init__.py" in status

    def test_fixtures_and_non_python_files_are_unchanged(self, repo):
        mm.main(["a.map"])

        assert (repo / "tests/fixtures/repo/app.py").read_text() == "import render\n"
        assert (repo / "notes.txt").read_text() == "import render\n"


class TestDryRun:
    def test_prints_the_rewrites_and_changes_nothing(self, repo, capsys):
        code = mm.main(["a.map", "--dry-run"])

        assert code == 0
        out = capsys.readouterr().out
        assert "scripts/main.py:1:" in out and "move scripts/render.py -> src/dossier/render/page.py" in out
        assert (repo / "scripts/render.py").exists()
        assert git(repo, "status", "--porcelain") == ""


class TestPreflight:
    def test_dirty_tree_is_refused(self, repo, capsys):
        (repo / "notes.txt").write_text("edited\n")

        assert mm.main(["a.map"]) == 2
        assert "dirty" in capsys.readouterr().err
        assert (repo / "scripts/render.py").exists()

    def test_missing_source_is_refused(self, repo, capsys):
        (repo / "a.map").write_text("nothere render.page\n")

        assert mm.main(["a.map", "--dry-run"]) == 2
        assert "does not exist" in capsys.readouterr().err

    def test_existing_destination_is_refused(self, repo, capsys):
        (repo / "src/dossier/render").mkdir(parents=True)
        (repo / "src/dossier/render/page.py").write_text("")

        assert mm.main(["a.map", "--dry-run"]) == 2
        assert "already exists" in capsys.readouterr().err


class TestCheck:
    def test_finds_a_leftover_import(self, repo, capsys):
        code = mm.main(["a.map", "--check"])

        assert code == 1
        out = capsys.readouterr().out
        assert "scripts/main.py:1:" in out and "tests/unit/test_x.py:4:" in out
        assert "fixtures" not in out

    def test_passes_after_the_move(self, repo, capsys):
        mm.main(["a.map"])
        git(repo, "add", "-A")

        assert mm.main(["a.map", "--check"]) == 0
