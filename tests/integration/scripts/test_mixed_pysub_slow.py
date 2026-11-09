import json
import os
from pathlib import Path

import pytest

import buildlog
import candidates
import stages
import workarea
from conftest import build_mixed_pysub_repo

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")

LANGS = ["Python", "TypeScript", "JavaScript", "JSON", "Shell", "YAML"]
SNAPSHOTS = Path(__file__).resolve().parents[2] / "fixtures" / "py_snapshot"


@pytest.fixture(scope="module")
def mixed(tmp_path_factory):
    base = tmp_path_factory.mktemp("mixedsub")
    repo = build_mixed_pysub_repo(base)
    patch = pytest.MonkeyPatch()
    for key, value in (("DOSSIER_HOME", base / "home"), ("DOSSIER_CONFIG", base / "cfg.json"), ("DOSSIER_CACHE", base / "cache")):
        patch.setenv(key, str(value))
    out = base / "home" / "mixedsub"
    area = workarea.area_for("mixedsub", repo.path, repo.sha, base / "cache")
    checkout = workarea.ensure_checkout(area, repo.path, repo.sha)["path"]
    tree = stages.tree_at(repo.path, repo.sha)
    build = buildlog.start(out, repo="mixedsub", sha=repo.sha, ref="main", version="test", options={})
    record = stages.stage_extract(build, repo.path, repo.sha, area, out, LANGS, workarea.trusted(repo.path, repo.sha), stages.Options(no_restore=True), {}, tree, checkout)
    try:
        yield record, out, tree
    finally:
        patch.undo()


def sections(out, output):
    return json.loads((out / "extract" / f"{output}.json").read_text())["adapters"]


def python_items(out, output):
    return sections(out, output).get("python", {}).get("items", [])


class TestMixedPythonSubfolder:
    def test_python_and_js_sections_exist(self, mixed):
        record, out, _ = mixed

        assert record["status"] == "ok" and {"python", "js"} <= set(sections(out, "graph"))

    def test_grimp_found_the_package_in_backend(self, mixed):
        record, _, _ = mixed

        tools = {a["name"]: a["tools"] for a in record["details"]["adapters"]}["python"]
        assert tools["grimp"]["status"] == "ok"

    def test_module_names_are_those_of_the_fixture_built_alone_with_paths_under_backend(self, mixed):
        _, out, _ = mixed
        alone = json.loads((SNAPSHOTS / "graph.json").read_text())

        got = {(g["module"], g["path"]) for g in python_items(out, "graph") if g["kind"] == "module"}

        assert got == {(g["module"], "backend/" + g["path"]) for g in alone if g["kind"] == "module"}

    def test_console_scripts_cite_the_backend_manifest(self, mixed):
        _, out, _ = mixed

        scripts = [e for e in python_items(out, "entry_points") if e["kind"] == "console-script"]

        assert scripts and {e["path"] for e in scripts} == {"backend/pyproject.toml"}

    def test_no_card_is_partial_for_grimp(self, mixed):
        record, _, _ = mixed

        tools = {a["name"]: a["tools"] for a in record["details"]["adapters"]}["python"]
        assert not [t for t, s in tools.items() if s["status"] != "ok"]

    def test_every_candidate_has_a_unique_id(self, mixed):
        _, out, _ = mixed
        extract = candidates.load(out)

        for output in candidates.ID_OUTPUTS:
            ids = [i["id"] for i in extract.get(output, []) if "id" in i]
            assert len(ids) == len(set(ids)), output

    def test_the_components_candidates_name_the_backend_project(self, mixed):
        _, out, tree = mixed

        text = candidates.text("components", candidates.load(out), {}, {}, tree=set(tree))

        assert "== Python packages ==" in text and "[backend]" in text
