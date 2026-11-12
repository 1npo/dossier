"""No tracked file names a path the package refactor retired (plan 014, block P).

Two kinds of stale path:

- skill paths that no longer exist anywhere (`scripts/<module>.py` other than the two launchers, `prompts/schema`,
  `tests/tools`, `scripts/eol.json`, ...). They are checked in every tracked text file.
- the old root folders `rules/`, `assets/` and `vendor/`. In code and tests these words mostly name folders of the
  repository being analysed (`vendor/x.py` is a path filter case), so they are checked only in Markdown, where they
  would name the skill's own files. Markdown inside `src/dossier/data/` names its sibling folders relative to
  itself, so it is skipped for this kind.

`docs/plans/` is history and keeps the paths of its time; fixtures and the vendored bundles are not ours to edit.
"""
import re
import subprocess

import pytest
from paths import SKILL_ROOT as ROOT

SKIPPED_FOLDERS = ("docs/plans/", "tests/fixtures/", "src/dossier/data/vendor/")

RETIRED = {
    "a flat module in scripts/": re.compile(r"scripts/(?!(?:dossier|check_page)\.py)[a-z_]+\.py"),
    "the old card schema folder": re.compile(r"prompts/schema"),
    "the old summary schema": re.compile(r"prompts/summary\.schema"),
    "the old test tools folder": re.compile(r"tests/tools"),
    "the old unit and integration folders": re.compile(r"tests/(?:unit|integration)/scripts"),
    "the old data files in scripts/": re.compile(r"scripts/(?:eol|tools)\.json"),
    "the old planning files": re.compile(r"docs/(?:process|post-v1)\.md|docs/prompts/"),
}
OLD_ROOT_FOLDER = re.compile(r"(?:^|[^/\w.-])(?:rules|assets|vendor)/")

# file -> why a retired path in it is not stale
ALLOWED_FILES = {
    "tests/content/test_paths.py": "this file spells out the patterns",
    "tests/unit/tools/test_move_modules.py": "the codemod's tests build a made-up skill whose modules live in scripts/",
    "tests/unit/dossier/findings/test_candidates_catalog.py": "scripts/x.py is a file of a made-up repository",
}
# (file, line number) -> why: lines that are inlined into every page, so they must not change
ALLOWED_LINES = {
    ("src/dossier/data/assets/dossier.css", 1): "the CSS is inlined in every page byte for byte",
}


def tracked_text_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    files = []
    for name in out.splitlines():
        if name.startswith(SKIPPED_FOLDERS) or not (ROOT / name).is_file():
            continue
        try:
            (ROOT / name).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        files.append(name)
    return files


def stale_lines(name: str, text: str) -> list[str]:
    if name in ALLOWED_FILES:
        return []
    check_root_folders = name.endswith(".md") and not name.startswith("src/dossier/data/")
    hits = []
    for number, line in enumerate(text.splitlines(), 1):
        if (name, number) in ALLOWED_LINES:
            continue
        kinds = [kind for kind, pattern in RETIRED.items() if pattern.search(line)]
        if check_root_folders and OLD_ROOT_FOLDER.search(line):
            kinds.append("an old root folder")
        hits += [f"{name}:{number}: {kind}" for kind in kinds]
    return hits


class TestStaleLines:
    @pytest.mark.parametrize(
        "line",
        [
            "run scripts/render.py",
            "see prompts/schema/README.md",
            "prompts/summary.schema.json",
            "tests/tools/m3_page.py",
            "tests/unit/scripts/test_x.py",
            "scripts/eol.json",
            "docs/process.md",
            "docs/prompts/plan-m0.md",
        ],
    )
    def test_retired_skill_path_is_reported(self, line):
        hits = stale_lines("src/dossier/x.py", line)

        assert hits != []

    @pytest.mark.parametrize("line", ["uv run scripts/dossier.py", "scripts/check_page.py", "src/dossier/data/rules/"])
    def test_current_path_is_not_reported(self, line):
        assert stale_lines("README.md", line) == []

    def test_old_root_folder_in_markdown_is_reported(self):
        assert stale_lines("docs/user-guide.md", "the rules in `rules/python/`") != []

    def test_old_root_folder_in_code_is_not_reported(self):
        assert stale_lines("tests/unit/x.py", 'write("vendor/x.py")') == []

    def test_markdown_inside_the_data_folder_names_siblings_relatively(self):
        assert stale_lines("src/dossier/data/README.md", "| `vendor/` | the bundles |") == []

    def test_allowed_line_is_not_reported(self):
        assert stale_lines("src/dossier/data/assets/dossier.css", "/* vendor/basecoat.min.css */\nscripts/x.py") == [
            "src/dossier/data/assets/dossier.css:2: a flat module in scripts/"
        ]


class TestRepositoryPaths:
    def test_no_tracked_file_names_a_retired_path(self):
        hits = [hit for name in tracked_text_files() for hit in stale_lines(name, (ROOT / name).read_text("utf-8"))]

        assert hits == []

    def test_every_allowed_file_exists(self):
        missing = [name for name in [*ALLOWED_FILES, *(f for f, _ in ALLOWED_LINES)] if not (ROOT / name).is_file()]

        assert missing == []
