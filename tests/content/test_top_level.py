"""The repository root holds only what D12 of plan 014 allows."""
import subprocess

from paths import SKILL_ROOT as ROOT

TRACKED_TOP_LEVEL = {
    ".claude-plugin",
    ".github",
    ".gitignore",
    "LICENSE",
    "README.md",
    "SKILL.md",
    "VERSION",
    "docs",
    "prompts",
    "pyproject.toml",
    "scripts",
    "src",
    "tests",
    "tools",
    "uv.lock",
}


class TestTopLevelLayout:
    def test_tracked_root_entries_are_exactly_the_allowed_list(self):
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        assert {line.split("/")[0] for line in out.splitlines()} == TRACKED_TOP_LEVEL
