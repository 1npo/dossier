import re
from pathlib import Path

import pytest

import candidates

SKILL = Path(__file__).resolve().parents[3]
RULES = SKILL / "rules"
TARGETS = SKILL / "tests" / "fixtures" / "semgrep"

IO_CATEGORIES = {"cli-args", "env-var", "config-file", "file-read", "stdin", "message-consume", "db-connect", "db-access",
                 "global-state", "cache", "thread", "async", "process-pool", "lock", "queue", "stdout", "file-write",
                 "outbound-call", "message-produce", "exit-code", "error-response", "log", "metric", "trace", "retry",
                 "timeout", "catch-all", "transaction", "request-header"}
OTHER_CATEGORIES = {"entry", "blindspot"}
BLIND_SPOTS = {"dynamic-import", "entry-point-loading", "string-plugin", "decorator-registry", "getattr-dispatch", "django-apps",
               "django-signals", "pytest-fixtures", "codegen", "feature-flag", "computed-subcommand",
               "dynamic-require", "barrel-reexport", "react-context", "hook-wiring", "string-route", "route-mount", "module-federation",
               "di-registration"}


def rule_files():
    return sorted(RULES.glob("*/*.yml"))


def read_rules(path: Path) -> list:
    """A tiny reader: collects id, category and blind-spot pattern per rule from `id:` and `metadata:` lines."""
    rules = []
    for line in path.read_text().splitlines():
        m = re.match(r"\s*- id:\s*(\S+)", line)
        if m:
            rules.append({"id": m.group(1), "category": None, "pattern": None})
        meta = re.search(r"metadata:\s*\{([^}]*)\}", line)
        if meta and rules:
            cat = re.search(r"category:\s*([\w-]+)", meta.group(1))
            pat = re.search(r"(?<![\w-])pattern:\s*([\w-]+)", meta.group(1))
            rules[-1]["category"] = cat.group(1) if cat else None
            rules[-1]["pattern"] = pat.group(1) if pat else None
    return rules


def annotations(target: Path, kind: str) -> set:
    found = set()
    for line in target.read_text().splitlines():
        m = re.match(rf"\s*(?:#|//)\s*{kind}:\s*(.+)$", line)
        if m:
            found |= {i.strip() for i in m.group(1).split(",")}
    return found


def cases():
    return [(f, r) for f in rule_files() for r in read_rules(f)]


def target_of(rule_file: Path) -> Path:
    folder = TARGETS / rule_file.parent.name
    return next((folder / (rule_file.stem + ext) for ext in (".py", ".ts", ".tsx", ".cs") if (folder / (rule_file.stem + ext)).exists()),
                folder / (rule_file.stem + ".py"))


class TestRuleFiles:
    def test_there_are_rule_files_for_every_scope(self):
        assert {f.parent.name for f in rule_files()} == {"python", "all", "js", "csharp"}

    @pytest.mark.parametrize("file,rule", cases(), ids=lambda v: v["id"] if isinstance(v, dict) else v.name)
    def test_id_starts_with_dossier_and_the_scope(self, file, rule):
        assert rule["id"].startswith(f"dossier.{file.parent.name}.")

    def test_ids_are_unique(self):
        ids = [r["id"] for _, r in cases()]

        assert len(ids) == len(set(ids))

    @pytest.mark.parametrize("file", rule_files(), ids=lambda f: f"{f.parent.name}/{f.name}")
    def test_every_rule_has_a_ruleid_and_an_ok_case_in_its_target_file(self, file):
        target = target_of(file)
        have_ruleid, have_ok = annotations(target, "ruleid"), annotations(target, "ok")

        ids = {r["id"] for r in read_rules(file)}
        assert ids <= have_ruleid and ids <= have_ok

    @pytest.mark.parametrize("file,rule", cases(), ids=lambda v: v["id"] if isinstance(v, dict) else v.name)
    def test_category_is_known(self, file, rule):
        assert rule["category"] in IO_CATEGORIES | OTHER_CATEGORIES

    def test_every_blind_spot_rule_names_a_listed_pattern(self):
        found = {r["pattern"] for f, r in cases() if r["category"] == "blindspot"}

        assert found == BLIND_SPOTS

    def test_every_category_of_the_design_has_a_rule(self):
        found = {r["category"] for _, r in cases()}

        assert IO_CATEGORIES <= found


class TestCategoryMap:
    def test_every_rule_category_has_a_home_card(self):
        found = {r["category"] for _, r in cases()} - OTHER_CATEGORIES

        assert found <= set(candidates.CATEGORY_CARD)

    def test_the_home_card_table_has_exactly_the_rule_categories(self):
        assert set(candidates.CATEGORY_CARD) == IO_CATEGORIES

    def test_every_home_card_is_a_card_in_the_schema(self):
        assert set(candidates.CATEGORY_CARD.values()) <= set(candidates.card_titles())
