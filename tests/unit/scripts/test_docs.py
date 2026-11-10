import argparse
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import dossier  # noqa: E402

PENDING = "docs arrive in M6-35 to M6-38"
STALE_NAMES = re.compile(
    r"(?i)\b(capabilities|interfaces|architecture|domain logic|code tour|failures|delivery)\s+report\b"
    r"|(?i:twelve reports)"
    r"|(?i:the contributors report has a card)"
)
CHECKED_FILES = [
    "README.md",
    "SKILL.md",
    "prompts/method.md",
    "prompts/reports.md",
    "rules/README.md",
    "docs/user-guide.md",
    "docs/developer-guide.md",
]
PENDING_FILES = {"README.md", "docs/user-guide.md", "docs/developer-guide.md"}
# Flags the user never types: Claude passes them or answers them through a question.
NOT_IN_BUILD_HINT = {"--chunk-tokens", "--restore"}


def subcommands(parser: argparse.ArgumentParser) -> dict:
    action = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return action.choices


def options_of(sub: argparse.ArgumentParser) -> list:
    return [o for a in sub._actions for o in a.option_strings if o not in ("-h", "--help")]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def hint_commands() -> list:
    hint = re.search(r"^argument-hint: (.*)$", read("SKILL.md"), re.M).group(1)
    return [part.strip().split()[0] for part in hint.split(" | ")]


class TestUserGuideNamesTheCli:
    @pytest.mark.xfail(strict=True, reason=PENDING)
    def test_every_subcommand_and_option_appears(self):
        guide = read("docs/user-guide.md")
        missing = []
        for name, sub in subcommands(dossier.build_parser()).items():
            if name not in guide:
                missing.append(name)
            missing += [o for o in options_of(sub) if o not in guide]

        assert missing == []


class TestSkillMatchesItsHint:
    def test_every_hinted_command_has_a_section(self):
        skill = read("SKILL.md")

        missing = [c for c in hint_commands() if f"### `/dossier {c}" not in skill]

        assert missing == []

    def test_build_hint_lists_every_flag_a_user_may_pass(self):
        hint = re.search(r"^argument-hint: (.*)$", read("SKILL.md"), re.M).group(1)
        prepare = subcommands(dossier.build_parser())["prepare"]

        missing = [o for o in options_of(prepare) if o not in NOT_IN_BUILD_HINT and o not in hint]

        assert missing == []


class TestNoStaleNames:
    @pytest.mark.parametrize(
        "name",
        [
            pytest.param(n, marks=pytest.mark.xfail(strict=True, reason=PENDING)) if n in PENDING_FILES else n
            for n in CHECKED_FILES
        ],
    )
    def test_file_has_no_retired_report_name(self, name):
        text = read(name)

        found = [m.group(0) for m in STALE_NAMES.finditer(text)]

        assert found == []
