import json
import os

import pytest

import buildlog
import stages
import workarea
from conftest import build_js_repo

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")


@pytest.fixture(scope="module")
def ex(tmp_path_factory):
    """One extraction of the JavaScript fixture repository with the adapter frame (the tool steps are not built yet)."""
    base = tmp_path_factory.mktemp("jsadapter")
    patch = pytest.MonkeyPatch()
    patch.setenv("DOSSIER_HOME", str(base / "home"))
    patch.setenv("DOSSIER_CONFIG", str(base / "cfg.json"))
    patch.setenv("DOSSIER_CACHE", str(base / "cache"))
    try:
        repo = build_js_repo(base)
        out = base / "home" / "jsrepo"
        area = workarea.area_for("jsrepo", repo.path, repo.sha, base / "cache")
        checkout = workarea.ensure_checkout(area, repo.path, repo.sha)["path"]
        build = buildlog.start(out, repo="jsrepo", sha=repo.sha, ref="main", version="test", options={})
        record = stages.stage_extract(build, repo.path, repo.sha, area, out, ["TypeScript", "JavaScript", "JSON"],
                                      workarea.trusted(repo.path, repo.sha), stages.Options(no_restore=True), {},
                                      stages.tree_at(repo.path, repo.sha), checkout)
        yield repo, out, record
    finally:
        patch.undo()


class TestJsAdapterFrame:
    def test_entry_points_have_a_js_section_with_the_package_entries(self, ex):
        repo, out, record = ex

        data = json.loads((out / "extract" / "entry_points.json").read_text())
        items = data["adapters"]["js"]["items"]

        assert record["status"] == "ok" and "js" in data["adapters"]
        bin_item = next(i for i in items if i["kind"] == "package-bin")
        assert (bin_item["name"], bin_item["path"], bin_item["id"].startswith("ep-")) == ("shopjs", "package.json", True)
        assert {"nx-target", "package-script", "http-route"} <= {i["kind"] for i in items}

    def test_the_adapter_records_each_tool_as_skipped_not_missing(self, ex):
        _, _, record = ex

        js = next(a for a in record["details"]["adapters"] if a["name"] == "js")

        assert set(js["tools"]) == {"dependency-cruiser", "knip", "scip-typescript", "typescript", "semgrep", "tree-sitter-language-pack"}
        assert {t["status"] for t in js["tools"].values()} == {"skipped"}
