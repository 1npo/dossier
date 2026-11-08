import json
import os
import shutil

import pytest

import buildlog
import candidates
import stages
import workarea
from conftest import CSFIX, JSFIX, _commit_fixture

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")

LANGS = ["C#", "TypeScript", "JavaScript", "JSON", "Shell", "YAML"]


@pytest.fixture(scope="module")
def mixed(tmp_path_factory):
    """One extraction of the C# fixture in `backend/` next to the TypeScript fixture's web package in `frontend/` (plan 011, M5-27)."""
    base = tmp_path_factory.mktemp("mixed-cs")
    parts = base / "parts"
    shutil.copytree(CSFIX, parts / "backend", ignore=shutil.ignore_patterns("bin", "obj"))
    shutil.copytree(JSFIX / "packages" / "web", parts / "frontend", ignore=shutil.ignore_patterns("node_modules"))
    repo = _commit_fixture(parts, base, "mixedcs")
    patch = pytest.MonkeyPatch()
    for key, value in (("DOSSIER_HOME", base / "home"), ("DOSSIER_CONFIG", base / "cfg.json"), ("DOSSIER_CACHE", base / "cache")):
        patch.setenv(key, str(value))
    out = base / "home" / "mixedcs"
    area = workarea.area_for("mixedcs", repo.path, repo.sha, base / "cache")
    checkout = workarea.ensure_checkout(area, repo.path, repo.sha)["path"]
    tree = stages.tree_at(repo.path, repo.sha)
    build = buildlog.start(out, repo="mixedcs", sha=repo.sha, ref="main", version="test", options={})
    record = stages.stage_extract(build, repo.path, repo.sha, area, out, LANGS, workarea.trusted(repo.path, repo.sha), stages.Options(no_restore=True), {}, tree, checkout)
    try:
        yield record, out, tree
    finally:
        patch.undo()


def sections(out, output):
    return json.loads((out / "extract" / f"{output}.json").read_text())["adapters"]


class TestMixedCSharpRepository:
    def test_the_extraction_has_a_section_for_csharp_js_and_repo(self, mixed):
        record, out, _ = mixed

        assert record["status"] == "ok"
        assert {"csharp", "js", "repo"} <= set(sections(out, "entry_points"))
        assert {"csharp", "js"} <= set(sections(out, "graph"))

    def test_the_two_languages_modules_do_not_clash(self, mixed):
        _, out, _ = mixed

        modules = [g["module"] for adapter in sections(out, "graph").values() for g in adapter["items"] if g["kind"] == "module"]

        assert len(modules) == len(set(modules))
        assert any(m.startswith("backend/") for m in modules) and any(m.startswith("frontend/") for m in modules)

    def test_every_candidate_has_a_unique_id(self, mixed):
        _, out, _ = mixed
        extract = candidates.load(out)

        for output in candidates.ID_OUTPUTS:
            ids = [i["id"] for i in extract.get(output, []) if "id" in i]
            assert len(ids) == len(set(ids)), output

    def test_the_components_report_lists_csharp_and_javascript_projects(self, mixed):
        _, out, tree = mixed

        text = candidates.text("components", candidates.load(out), {}, {}, tree=set(tree))

        assert "== C# projects ==" in text and "== JavaScript and TypeScript projects ==" in text
        assert "backend/src/Shop.Core/Shop.Core.csproj" in text
