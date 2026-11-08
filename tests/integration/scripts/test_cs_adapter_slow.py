import json
import os
import shutil
from types import SimpleNamespace

import pytest

import buildlog
import stages
import workarea
from adapters import OUTPUTS
from conftest import build_cs_repo

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")


def _build(base_dir):
    patch = pytest.MonkeyPatch()
    patch.setenv("DOSSIER_HOME", str(base_dir / "home"))
    patch.setenv("DOSSIER_CONFIG", str(base_dir / "cfg.json"))
    patch.setenv("DOSSIER_CACHE", str(base_dir / "cache"))
    repo = build_cs_repo(base_dir)
    out = base_dir / "home" / "csrepo"
    area = workarea.area_for("csrepo", repo.path, repo.sha, base_dir / "cache")
    checkout = workarea.ensure_checkout(area, repo.path, repo.sha)["path"]
    build = buildlog.start(out, repo="csrepo", sha=repo.sha, ref="main", version="test", options={})
    record = stages.stage_extract(build, repo.path, repo.sha, area, out, ["C#"], workarea.trusted(repo.path, repo.sha), stages.Options(no_restore=True), {}, stages.tree_at(repo.path, repo.sha), checkout)
    return patch, SimpleNamespace(repo=repo, out=out, record=record)


@pytest.fixture(scope="module")
def extraction(tmp_path_factory):
    patch, got = _build(tmp_path_factory.mktemp("csadapter"))
    try:
        yield got
    finally:
        patch.undo()
        shutil.rmtree(got.out.parent.parent, ignore_errors=True)


def _items(ex, name):
    return json.loads((ex.out / "extract" / f"{name}.json").read_text())["adapters"]["csharp"]["items"]


class TestCSharpSection:
    def test_every_output_has_a_csharp_section(self, extraction):
        for name in OUTPUTS:
            assert (extraction.out / "extract" / f"{name}.json").exists()
            assert "csharp" in json.loads((extraction.out / "extract" / f"{name}.json").read_text())["adapters"]

    def test_graph_has_modules_imports_and_projects(self, extraction):
        kinds = {i["kind"] for i in _items(extraction, "graph")}

        assert {"module", "import", "cs-project", "project-reference", "cs-note"} <= kinds

    def test_order_links_to_the_customer_and_the_status_it_uses(self, extraction):
        edges = {(i["path"], i["paths"][0]) for i in _items(extraction, "graph") if i["kind"] == "import"}

        assert {("src/Shop.Core/Order.cs", "src/Shop.Core/Customer.cs"), ("src/Shop.Core/Order.cs", "src/Shop.Core/OrderStatus.cs")} <= edges

    def test_entry_points_models_tests_and_blind_spots_are_filled(self, extraction):
        assert {"http-route", "program-main", "hosted-service", "function", "ui-route", "signalr-hub", "build-target"} <= {i["kind"] for i in _items(extraction, "entry_points")}
        assert {"ef-entity", "cs-enum", "migration"} <= {i["kind"] for i in _items(extraction, "models")}
        assert {"test-file"} <= {i["kind"] for i in _items(extraction, "tests")}
        assert {"di-registration", "codegen", "mediator-handler"} <= {i["pattern"] for i in _items(extraction, "blindspots")}
        assert {"db-connect", "env-var", "global-state"} <= {i["category"] for i in _items(extraction, "io_candidates")}

    def test_symbols_and_dead_are_empty_until_scip_dotnet_arrives(self, extraction):
        assert _items(extraction, "symbols") == [] and _items(extraction, "dead") == []

    def test_tree_sitter_and_semgrep_are_ok_and_scip_dotnet_is_skipped(self, extraction):
        cs = next(a for a in extraction.record["details"]["adapters"] if a["name"] == "csharp")

        assert set(cs["tools"]) == {"scip-dotnet", "semgrep", "tree-sitter-language-pack"}
        assert cs["tools"]["tree-sitter-language-pack"]["status"] == "ok" and cs["tools"]["semgrep"]["status"] == "ok"
        assert cs["tools"]["scip-dotnet"]["status"] == "skipped"
