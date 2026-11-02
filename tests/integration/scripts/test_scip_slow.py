import functools
import os
from pathlib import Path

import pytest

import scip_read
import scip_tool
import sandbox
import toolcheck

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")


@pytest.fixture
def indexed(tmp_path, py_repo):
    area = tmp_path / "cache" / "repo"
    area.mkdir(parents=True)
    run = functools.partial(sandbox.run, area=area, cwd=Path(py_repo.path), timeout=900)
    version = next(t["version"] for t in toolcheck.load_tools()["tools"] if t["id"] == "scip-python")
    index_js = scip_tool.ensure_installed(run, area.parent, version, 900)
    index = scip_tool.run_index(run, index_js, Path(py_repo.path), area, "shopcart", py_repo.sha, 900)
    return scip_read.reduce(scip_read.decode(index.read_bytes()))


class TestScipOnTheFixture:
    def test_definitions_include_a_public_total_and_unused_helper(self, indexed):
        defs = {i["name"]: i for i in indexed if i["kind"] == "def" and i["path"] == "src/shopcart/core.py"}

        assert defs["total"]["public"] is True and defs["total"]["type"] == "function"
        assert "unused_helper" in defs

    def test_cli_references_core(self, indexed):
        edges = [i for i in indexed if i["kind"] == "ref-edge"]

        assert any(e["path"] == "src/shopcart/cli.py" and e["paths"] == ["src/shopcart/core.py"] for e in edges)

    def test_no_index_file_is_left_in_the_checkout(self, indexed, py_repo):
        assert not list(Path(py_repo.path).rglob("*.scip"))
