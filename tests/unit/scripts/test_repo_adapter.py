import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import repo_adapter


class FakeSemgrep:
    def __init__(self, results=None, error=None):
        self.results, self.error, self.calls = results or [], error, []

    def scan(self, config, paths=None, timeout=30):
        self.calls.append((config, paths))
        if self.error:
            raise self.error
        return self.results


class TestDockerfileEntries:
    def test_cmd_and_entrypoint_lines_become_container_entries(self):
        got = repo_adapter.dockerfile_entries("Dockerfile", 'FROM x\nENTRYPOINT ["tini"]\nCMD ["python", "-m", "app"]\n')

        assert [(e["line"], e["kind"], e["name"], e["target"]) for e in got] == [
            (2, "container", "ENTRYPOINT", '["tini"]'), (3, "container", "CMD", '["python", "-m", "app"]')]

    def test_other_instructions_are_ignored(self):
        assert repo_adapter.dockerfile_entries("Dockerfile", "FROM x\nRUN make\nCOPY . /app\n") == []

    def test_entry_has_the_full_set_of_fields(self):
        e = repo_adapter.dockerfile_entries("Dockerfile", "CMD run\n")[0]

        assert (e["rule"], e["trigger"], e["end_line"], e["snippet"]) == ("repo.container", "When the container starts", 1, "CMD run")


class TestMakefileTargets:
    def test_targets_are_listed_and_special_ones_are_not(self):
        text = ".PHONY: test\nCC := gcc\ntest:  # run tests\n\tpytest\nbuild-all: deps\n\tmake\n"

        got = repo_adapter.makefile_targets("Makefile", text)

        assert [(e["line"], e["name"], e["target"]) for e in got] == [(3, "test", "make test"), (5, "build-all", "make build-all")]

    def test_recipe_lines_are_not_targets(self):
        assert repo_adapter.makefile_targets("Makefile", "all:\n\techo a: b\n") [0]["name"] == "all"


class TestWorkflowEntries:
    GITHUB = ('on:\n  schedule:\n    - cron: "0 3 * * *"  # nightly\njobs:\n  t:\n    steps:\n      - run: pytest -q  # tests\n'
              '      - run: ruff check .\n      - run: |\n          echo hi\n          make test\n      - run: make lint\n')

    def test_cron_line_is_a_schedule_entry(self):
        got = [e for e in repo_adapter.workflow_entries(".github/workflows/ci.yml", self.GITHUB) if e["kind"] == "ci-schedule"]

        assert [(e["line"], e["name"]) for e in got] == [(3, "0 3 * * *")]

    def test_test_commands_are_found_on_run_lines_and_in_blocks(self):
        got = [e for e in repo_adapter.workflow_entries(".github/workflows/ci.yml", self.GITHUB) if e["kind"] == "ci-command"]

        assert [(e["line"], e["command"]) for e in got] == [(7, "pytest -q"), (11, "make test")]

    def test_gitlab_script_items_are_commands(self):
        text = "test:\n  script:\n    - pip install .\n    - tox -e py\n"

        got = repo_adapter.workflow_entries(".gitlab-ci.yml", text)

        assert [(e["kind"], e["command"]) for e in got] == [("ci-command", "tox -e py")]


class TestSystemdUnits:
    def test_exec_start_gives_one_entry(self):
        got = repo_adapter.systemd_units("deploy/app.service", "[Service]\nExecStart=/usr/bin/app --serve\n")

        assert [(e["kind"], e["line"], e["name"], e["target"]) for e in got] == [("systemd-unit", 2, "app.service", "/usr/bin/app --serve")]

    def test_unit_without_exec_start_gives_nothing(self):
        assert repo_adapter.systemd_units("a.service", "[Unit]\nDescription=x\n") == []


class TestShebangScripts:
    def test_first_line_shebang_gives_an_entry_at_line_one(self):
        got = repo_adapter.shebang_scripts("scripts/seed.sh", "#!/bin/sh\necho seed\n")

        assert [(e["line"], e["name"], e["target"]) for e in got] == [(1, "seed.sh", "/bin/sh")]

    def test_file_without_shebang_gives_nothing(self):
        assert repo_adapter.shebang_scripts("run.sh", "echo hi\n") == []

    def test_empty_file_gives_nothing(self):
        assert repo_adapter.shebang_scripts("run.sh", "") == []


class TestSqlTables:
    def test_create_table_gives_an_entity_with_columns(self):
        text = "-- schema\nCREATE TABLE IF NOT EXISTS shop.orders (\n  id INTEGER PRIMARY KEY,\n  user_id INT REFERENCES users(id),\n  PRIMARY KEY (id)\n);\n"

        got = repo_adapter.sql_tables("db/schema.sql", text)

        assert len(got) == 1
        t = got[0]
        assert (t["name"], t["kind"], t["line"], t["end_line"], t["rule"]) == ("orders", "sql-table", 2, 6, "repo.sql-table")
        assert [(f["name"], f["type"], f["line"], f["ref"]) for f in t["fields"]] == [("id", "INTEGER", 3, None), ("user_id", "INT", 4, "users")]

    def test_one_line_table(self):
        got = repo_adapter.sql_tables("db/schema.sql", "CREATE TABLE orders (id INTEGER PRIMARY KEY);\n")

        assert got[0]["fields"] == [{"name": "id", "type": "INTEGER", "line": 1, "ref": None, "pk": True}]

    def test_sql_file_in_a_migrations_folder_is_one_migration_item(self):
        got = repo_adapter.sql_tables("db/migrations/001_init.sql", "CREATE TABLE a (id INT);\n")

        assert got == [{"path": "db/migrations/001_init.sql", "kind": "migration", "tool": "sql", "rule": "repo.migration"}]

    def test_no_create_table_gives_nothing(self):
        assert repo_adapter.sql_tables("q.sql", "SELECT 1;\n") == []


SCRAPES = """CREATE TABLE scrapes (
    id             INTEGER PRIMARY KEY,
    run_id         INTEGER NOT NULL REFERENCES runs(id),
    shop           TEXT NOT NULL,      -- internal store key
    site           TEXT NOT NULL,
    store          TEXT NOT NULL,
    menu           TEXT NOT NULL CHECK (menu IN ('adult-use', 'medical')),
    platform       TEXT,
    status         TEXT NOT NULL CHECK (status IN ('ok', 'partial', 'failed')),
    expected_count INTEGER,
    product_count  INTEGER NOT NULL,
    errors         TEXT NOT NULL,      -- JSON array
    started_at     TEXT NOT NULL,
    finished_at    TEXT NOT NULL
);
"""


class TestSqlColumns:
    def test_comments_do_not_become_columns_or_hide_the_next_one(self):
        got = repo_adapter.sql_tables("db/schema.sql", SCRAPES)[0]

        assert [f["name"] for f in got["fields"]] == ["id", "run_id", "shop", "site", "store", "menu", "platform", "status",
                                                      "expected_count", "product_count", "errors", "started_at", "finished_at"]

    def test_line_numbers_still_point_at_the_column(self):
        got = repo_adapter.sql_tables("db/schema.sql", SCRAPES)[0]

        assert {f["name"]: f["line"] for f in got["fields"]}["site"] == 5

    def test_a_block_comment_and_a_comment_with_a_comma_are_ignored(self):
        text = "CREATE TABLE t (\n  a INT, /* one, two */\n  b INT -- x, y\n);\n"

        got = repo_adapter.sql_tables("s.sql", text)[0]

        assert [f["name"] for f in got["fields"]] == ["a", "b"]

    def test_an_unbalanced_bracket_in_a_comment_does_not_end_the_table_late(self):
        text = "CREATE TABLE t (\n  a INT, -- see (note\n  b INT\n);\nCREATE TABLE u (c INT);\n"

        got = repo_adapter.sql_tables("s.sql", text)

        assert [t["name"] for t in got] == ["t", "u"]
        assert [f["name"] for f in got[0]["fields"]] == ["a", "b"]

    def test_inline_and_table_level_foreign_keys_become_relations(self):
        text = "CREATE TABLE t (\n  run_id INTEGER REFERENCES runs(id),\n  a INT,\n  FOREIGN KEY (a) REFERENCES other(b)\n);\n"

        got = repo_adapter.sql_tables("s.sql", text)[0]

        assert got["relations"] == [{"field": "run_id", "to": "runs", "kind": "fk"}, {"field": "a", "to": "other", "kind": "fk"}]
        assert {f["name"]: f["ref"] for f in got["fields"]} == {"run_id": "runs", "a": "other"}

    def test_table_level_primary_key_marks_every_listed_column(self):
        text = "CREATE TABLE t (\n  x INT,\n  y INT,\n  z INT,\n  PRIMARY KEY (x, y)\n);\n"

        got = repo_adapter.sql_tables("s.sql", text)[0]

        assert [f["name"] for f in got["fields"] if f.get("pk")] == ["x", "y"]

    def test_a_table_without_foreign_keys_has_an_empty_relations_list(self):
        assert repo_adapter.sql_tables("s.sql", "CREATE TABLE t (a INT);\n")[0]["relations"] == []

    def test_the_real_scrapes_table_has_one_relation(self):
        got = repo_adapter.sql_tables("db/schema.sql", SCRAPES)[0]

        assert got["relations"] == [{"field": "run_id", "to": "runs", "kind": "fk"}]


def context(py_repo, semgrep):
    tree = frozenset(subprocess.run(["git", "-C", py_repo.path, "ls-files"], capture_output=True, text=True).stdout.split())
    return SimpleNamespace(checkout=Path(py_repo.path), sha=py_repo.sha, tree=tree, semgrep=semgrep, tool_status={})


class TestExtract:
    @pytest.fixture
    def out(self, py_repo):
        return repo_adapter.RepoAdapter().extract(context(py_repo, FakeSemgrep()))

    def test_entry_points_are_the_five_from_non_language_files(self, out, py_repo):
        got = {(e["kind"], e["path"], e["line"]) for e in out["entry_points"]}

        assert got == {("container", "Dockerfile", py_repo.line_of("Dockerfile", "ep-docker") + 1),
                       ("make-target", "Makefile", py_repo.line_of("Makefile", "ep-make")),
                       ("ci-schedule", ".github/workflows/ci.yml", py_repo.line_of(".github/workflows/ci.yml", "ep-cron")),
                       ("shebang-script", "scripts/seed.sh", 1)}

    def test_sql_table_is_an_entity(self, out):
        assert [(m["name"], m["kind"]) for m in out["models"]] == [("orders", "sql-table")]

    def test_ci_command_is_a_test_item(self, out, py_repo):
        assert [(t["kind"], t["command"], t["line"]) for t in out["tests"]] == [
            ("ci-command", "pytest -q", py_repo.line_of(".github/workflows/ci.yml", "ci-pytest"))]

    def test_blind_spots_come_from_the_all_rules(self, py_repo):
        results = [{"rule": "dossier.all.blindspot.codegen", "path": "a.py", "start_line": 1, "end_line": 1, "snippet": "# generated",
                    "metadata": {"pattern": "codegen"}}]
        semgrep = FakeSemgrep(results)

        out = repo_adapter.RepoAdapter().extract(context(py_repo, semgrep))

        assert out["blindspots"] == [{"path": "a.py", "line": 1, "end_line": 1, "pattern": "codegen", "rule": "dossier.all.blindspot.codegen",
                                      "snippet": "# generated"}]
        config, paths = semgrep.calls[0]
        assert config == repo_adapter.RULES_ALL and "tests/test_core.py" in paths and "README.md" not in paths

    def test_semgrep_failure_is_recorded_and_the_rest_is_kept(self, py_repo):
        ctx = context(py_repo, FakeSemgrep(error=RuntimeError("boom\nmore")))

        out = repo_adapter.RepoAdapter().extract(ctx)

        assert ctx.tool_status["semgrep"] == {"status": "failed", "reason": "boom"} and out["entry_points"]

    def test_semgrep_success_is_recorded(self, py_repo):
        ctx = context(py_repo, FakeSemgrep())

        repo_adapter.RepoAdapter().extract(ctx)

        assert ctx.tool_status["semgrep"]["status"] == "ok"

    def test_adapter_matches_every_language(self):
        assert repo_adapter.RepoAdapter.languages == ("*",)


class TestTestCommand:
    @pytest.mark.parametrize("command", ["pytest -q", "tox", "make test", "npx jest --ci", "vitest run", "mocha tests", "npx playwright test",
                                         "cypress run", "npm test", "npm run test", "yarn test", "pnpm run test", "nx test web", "npm run test-e2e"])
    def test_a_test_command_is_recognised(self, command):
        assert repo_adapter.TEST_COMMAND.search(command)

    @pytest.mark.parametrize("command", ["npm run build", "npm install", "yarn lint", "pnpm dev", "echo done"])
    def test_other_commands_are_not(self, command):
        assert not repo_adapter.TEST_COMMAND.search(command)

    def test_the_adapter_version_changed_with_the_pattern(self):
        assert repo_adapter.RepoAdapter.version == "3"
