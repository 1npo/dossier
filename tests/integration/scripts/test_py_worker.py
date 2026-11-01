import functools
import os
from pathlib import Path

import pytest

import py_packages
import py_tools
import sandbox

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")


@pytest.fixture
def run(tmp_path, py_repo):
    area = tmp_path / "cache" / "repo"
    area.mkdir(parents=True)
    return functools.partial(sandbox.run, area=area, cwd=Path(py_repo.path), timeout=600)


@pytest.fixture
def graph(run, py_repo):
    contracts = py_packages.importlinter_contracts(Path(py_repo.path))["contracts"]
    return py_tools.Grimp(run, 600).graph([str(Path(py_repo.path) / "src")], ["shopcart"], contracts)


class TestGrimpWorker:
    def test_modules_include_the_fixture_modules(self, graph):
        names = {m["module"] for m in graph["modules"]}

        assert {"shopcart.core", "shopcart.a", "shopcart.b"} <= names

    def test_module_paths_are_files_in_the_checkout(self, graph, py_repo):
        core = next(m for m in graph["modules"] if m["module"] == "shopcart.core")

        assert core["path"] == str(Path(py_repo.path) / "src/shopcart/core.py") and core["is_package"] is False

    def test_cycle_import_is_found_at_its_line(self, graph, py_repo):
        edge = next(i for i in graph["imports"] if (i["from"], i["to"]) == ("shopcart.a", "shopcart.b"))

        assert edge["lines"] == [py_repo.line_of("src/shopcart/a.py", "cycle-a")]

    def test_upward_import_is_found_at_its_line(self, graph, py_repo):
        edge = next(i for i in graph["imports"] if (i["from"], i["to"]) == ("shopcart.core", "shopcart.cli"))

        assert edge["lines"] == [py_repo.line_of("src/shopcart/core.py", "import-up")]

    def test_layers_contract_is_broken_with_the_violation(self, graph, py_repo):
        contract = next(c for c in graph["contracts"] if c["name"] == "cli above core")

        assert contract["status"] == "broken"
        assert {"from": "shopcart.core", "to": "shopcart.cli", "line": py_repo.line_of("src/shopcart/core.py", "import-up")} \
            in contract["violations"]

    def test_independence_contract_is_not_checked(self, graph):
        contract = next(c for c in graph["contracts"] if c["name"] == "apps apart")

        assert contract["status"] == "not-checked" and "layers and forbidden" in contract["reason"]

    def test_no_grimp_cache_is_left_in_the_checkout(self, graph, py_repo):
        assert not (Path(py_repo.path) / ".grimp_cache").exists()


class TestVultureWorker:
    def test_unused_function_is_reported_at_its_line(self, run, py_repo):
        files = ["src/shopcart/core.py", "src/shopcart/store.py"]

        items = py_tools.Vulture(run, 600).dead(files, {})

        hit = next(i for i in items if i["name"] == "unused_helper")
        assert hit["line"] == py_repo.line_of("src/shopcart/core.py", "dead-func") and hit["type"] == "function"


class TestForbiddenContract:
    def test_forbidden_import_is_a_violation_with_its_first_link(self, run, py_repo):
        contract = {"name": "no up", "type": "forbidden", "source_modules": ["shopcart.core"], "forbidden_modules": ["shopcart.cli"]}

        res = py_tools.Grimp(run, 600).graph([str(Path(py_repo.path) / "src")], ["shopcart"], [contract])

        got = res["contracts"][0]
        assert got["status"] == "broken" and got["violations"][0]["from"] == "shopcart.core"

    def test_unrelated_forbidden_modules_are_kept(self, run, py_repo):
        contract = {"name": "ok", "type": "forbidden", "source_modules": ["shopcart.store"], "forbidden_modules": ["shopcart.api"]}

        res = py_tools.Grimp(run, 600).graph([str(Path(py_repo.path) / "src")], ["shopcart"], [contract])

        assert res["contracts"][0]["status"] == "kept"
