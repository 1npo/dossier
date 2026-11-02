import json
import os
import subprocess
from pathlib import Path

import pytest

import buildlog
import stages
import workarea
from conftest import build_py_repo

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")


class Extracted:
    def __init__(self, tmp_path, py_repo):
        self.repo, self.tmp = py_repo, tmp_path
        self.top, self.sha = py_repo.path, py_repo.sha
        self.out = tmp_path / "home" / "pyrepo"
        self.area = workarea.area_for("pyrepo", self.top, self.sha, tmp_path / "cache")
        self.checkout = workarea.ensure_checkout(self.area, self.top, self.sha)["path"]
        self.tree = stages.tree_at(self.top, self.sha)
        self.build = buildlog.start(self.out, repo="pyrepo", sha=self.sha, ref="main", version="test", options={})

    def run(self):
        return stages.stage_extract(self.build, self.top, self.sha, self.area, self.out, ["Python", "Shell", "YAML"],
                                    workarea.trusted(self.top, self.sha), stages.Options(), {}, self.tree, self.checkout)

    def items(self, output):
        data = json.loads((self.out / "extract" / f"{output}.json").read_text())
        return [i for name in sorted(data["adapters"]) for i in data["adapters"][name]["items"]]

    def line(self, rel, name):
        return self.repo.line_of(rel, name)


@pytest.fixture(scope="module")
def ex(tmp_path_factory):
    """One real extraction of the fixture repository, shared by the tests below (it takes about half a minute)."""
    base = tmp_path_factory.mktemp("pyadapter")
    patch = pytest.MonkeyPatch()
    patch.setenv("DOSSIER_HOME", str(base / "home"))
    patch.setenv("DOSSIER_CONFIG", str(base / "cfg.json"))
    patch.setenv("DOSSIER_CACHE", str(base / "cache"))
    try:
        e = Extracted(base, build_py_repo(base))
        e.record = e.run()
        yield e
    finally:
        patch.undo()


class TestFixtureOfRecord:
    def test_extract_succeeds_with_every_tool_ok(self, ex):
        adapters = {a["name"]: a for a in ex.record["details"]["adapters"]}

        assert ex.record["status"] == "ok" and set(adapters) == {"python", "repo"}
        assert {t: s["status"] for a in adapters.values() for t, s in a["tools"].items()} == {
            "grimp": "ok", "tree-sitter-language-pack": "ok", "semgrep": "ok", "vulture": "ok", "scip-python": "ok"}

    def test_entry_points_are_exactly_the_ten_expected(self, ex):
        got = {(e["kind"], e["path"], e["line"]) for e in ex.items("entry_points")}

        expected = {("console-script", "pyproject.toml", ex.line("pyproject.toml", "ep-script")),
                    ("main-module", "src/shopcart/__main__.py", ex.line("src/shopcart/__main__.py", "ep-main-module")),
                    ("main-guard", "src/shopcart/cli.py", ex.line("src/shopcart/cli.py", "ep-guard")),
                    ("http-route", "src/shopcart/api.py", ex.line("src/shopcart/api.py", "ep-route")),
                    ("http-route", "src/shopcart/api.py", ex.line("src/shopcart/api.py", "ep-route2")),
                    ("container", "Dockerfile", ex.line("Dockerfile", "ep-docker") + 1),
                    ("make-target", "Makefile", ex.line("Makefile", "ep-make")),
                    ("ci-schedule", ".github/workflows/ci.yml", ex.line(".github/workflows/ci.yml", "ep-cron")),
                    ("shebang-script", "scripts/seed.sh", 1),
                    ("cli-command", "src/shopcart/cli.py", ex.line("src/shopcart/cli.py", "ep-subcommand"))}
        assert got == expected and len(ex.items("entry_points")) == 10

    def test_an_argparse_subcommand_is_a_cli_command_named_by_its_literal(self, ex):
        item = next(e for e in ex.items("entry_points") if e["kind"] == "cli-command")

        assert item["name"] == "seed" and item["trigger"] == "the `seed` command" and item["target"] == "src/shopcart/cli.py"

    def test_graph_has_the_cycle_the_broken_contract_and_the_unchecked_one(self, ex):
        graph = ex.items("graph")

        cycles = [g["modules"] for g in graph if g["kind"] == "cycle"]
        contracts = {g["contract"]: g for g in graph if g["kind"] == "contract"}
        assert ["shopcart.a", "shopcart.b"] in cycles
        assert contracts["cli above core"]["status"] == "broken"
        assert contracts["cli above core"]["violations"][0]["from"] == "shopcart.core"
        assert contracts["apps apart"]["status"] == "not-checked"

    def test_io_candidates_cover_the_expected_categories_at_their_lines(self, ex):
        got = {(c["category"], c["path"], c["line"]) for c in ex.items("io_candidates")}

        def at(cat, rel, marker):
            return (cat, rel, ex.line(rel, marker))
        expected = {at("cli-args", "src/shopcart/cli.py", "io-cli"), at("stdout", "src/shopcart/cli.py", "io-print"),
                    at("exit-code", "src/shopcart/cli.py", "io-exit"), at("log", "src/shopcart/core.py", "io-log-get"),
                    at("log", "src/shopcart/core.py", "io-log"),
                    at("env-var", "src/shopcart/store.py", "io-env"), at("db-connect", "src/shopcart/store.py", "io-db-connect"),
                    at("file-write", "src/shopcart/store.py", "io-file-write"), at("file-read", "src/shopcart/store.py", "io-file-read"),
                    at("outbound-call", "src/shopcart/store.py", "io-outbound"), at("timeout", "src/shopcart/store.py", "io-outbound"),
                    at("global-state", "src/shopcart/core.py", "state-module"), at("global-state", "src/shopcart/plugins.py", "state-registry"),
                    at("lock", "src/shopcart/worker.py", "cc-lock"), at("thread", "src/shopcart/worker.py", "cc-thread"),
                    at("async", "src/shopcart/worker.py", "cc-async")}
        assert expected <= got
        marker = ex.line("src/shopcart/core.py", "fail-catchall")
        assert any(c["category"] == "catch-all" and c["path"] == "src/shopcart/core.py" and c["line"] <= marker <= c["end_line"]
                   for c in ex.items("io_candidates"))
        assert ("file-read", "src/shopcart/store.py", ex.line("src/shopcart/store.py", "io-file-write")) not in got

    def test_env_var_candidate_names_the_variable(self, ex):
        env = [c for c in ex.items("io_candidates") if c["category"] == "env-var"]

        assert [c["detail"] for c in env] == ["SHOP_DB"]

    def test_models_are_the_three_classes_and_the_sql_table(self, ex):
        assert {(m["name"], m["kind"]) for m in ex.items("models") if m["kind"] != "migration"} == {
            ("Item", "dataclass"), ("Status", "enum"), ("Order", "pydantic"), ("orders", "sql-table")}

    def test_tests_output_has_the_file_the_configs_and_the_ci_command(self, ex):
        tests = ex.items("tests")

        assert [t["path"] for t in tests if t["kind"] == "test-file"] == ["tests/test_core.py"]
        assert {t["tool"] for t in tests if t["kind"] == "config"} == {"pytest", "coverage"}
        assert [t["command"] for t in tests if t["kind"] == "ci-command"] == ["pytest -q"]

    def test_dead_includes_the_unused_helper(self, ex):
        names = {d["name"]: d for d in ex.items("dead")}

        assert names["unused_helper"]["line"] == ex.line("src/shopcart/core.py", "dead-func")

    def test_blind_spots_are_found_at_their_lines(self, ex):
        got = {(b["pattern"], b["path"], b["line"]) for b in ex.items("blindspots")}

        assert {("dynamic-import", "src/shopcart/plugins.py", ex.line("src/shopcart/plugins.py", "bs-import")),
                ("getattr-dispatch", "src/shopcart/plugins.py", ex.line("src/shopcart/plugins.py", "bs-getattr")),
                ("decorator-registry", "src/shopcart/plugins.py", ex.line("src/shopcart/plugins.py", "bs-registry")),
                ("pytest-fixtures", "tests/test_core.py", ex.line("tests/test_core.py", "bs-fixture"))} <= got

    def test_symbols_have_the_defs_and_the_cli_to_core_edge(self, ex):
        symbols = ex.items("symbols")

        assert any(s["kind"] == "def" and s["name"] == "total" and s["public"] for s in symbols)
        assert any(s["kind"] == "ref-edge" and s["path"] == "src/shopcart/cli.py" and s["paths"] == ["src/shopcart/core.py"] for s in symbols)

    def test_every_candidate_has_an_id_and_a_group(self, ex):
        for output in ("entry_points", "io_candidates", "models", "dead", "blindspots"):
            assert all(i.get("id") and i.get("group") for i in ex.items(output)), output

    def test_second_run_is_reused(self, ex):
        assert ex.run()["status"] == "reused"

    def test_checkout_is_clean_with_no_cache_or_index_files(self, ex):
        status = subprocess.run(["git", "-C", str(ex.checkout), "status", "--porcelain", "--ignored"], capture_output=True, text=True).stdout

        assert status.strip() == ""
        assert not (Path(ex.checkout) / ".grimp_cache").exists() and not list(Path(ex.checkout).rglob("*.scip"))
