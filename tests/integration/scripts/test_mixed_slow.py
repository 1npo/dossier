import json
import os
import shutil

import pytest

import buildlog
import candidates
import stages
import workarea
from conftest import JSFIX, PYFIX, _commit_fixture

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")

LANGS = ["Python", "TypeScript", "JavaScript", "JSON", "Shell", "YAML"]


@pytest.fixture(scope="module")
def mixed(tmp_path_factory):
    """One extraction of a Python repository with a TypeScript frontend in `frontend/`, as D13 describes (plan 010).

    PYFIX stays at the root here. `test_mixed_pysub_slow.py` covers the same Python code under `backend/`.
    """
    base = tmp_path_factory.mktemp("mixed")
    parts = base / "parts"
    shutil.copytree(PYFIX, parts, ignore=shutil.ignore_patterns("__pycache__", "node_modules"))
    shutil.copytree(JSFIX / "packages" / "web", parts / "frontend", ignore=shutil.ignore_patterns("node_modules"))
    repo = _commit_fixture(parts, base, "mixed")
    patch = pytest.MonkeyPatch()
    for key, value in (("DOSSIER_HOME", base / "home"), ("DOSSIER_CONFIG", base / "cfg.json"), ("DOSSIER_CACHE", base / "cache")):
        patch.setenv(key, str(value))
    out = base / "home" / "mixed"
    area = workarea.area_for("mixed", repo.path, repo.sha, base / "cache")
    checkout = workarea.ensure_checkout(area, repo.path, repo.sha)["path"]
    tree = stages.tree_at(repo.path, repo.sha)
    build = buildlog.start(out, repo="mixed", sha=repo.sha, ref="main", version="test", options={})
    record = stages.stage_extract(build, repo.path, repo.sha, area, out, LANGS, workarea.trusted(repo.path, repo.sha), stages.Options(no_restore=True), {}, tree, checkout)
    try:
        yield record, out, tree
    finally:
        patch.undo()


def sections(out, output):
    return json.loads((out / "extract" / f"{output}.json").read_text())["adapters"]


class TestMixedRepository:
    def test_the_extraction_has_a_section_for_each_adapter(self, mixed):
        record, out, _ = mixed

        assert record["status"] == "ok"
        assert {"js", "python", "repo"} <= set(sections(out, "entry_points"))
        assert {"js", "python"} <= set(sections(out, "graph"))

    def test_the_two_languages_modules_do_not_clash(self, mixed):
        _, out, _ = mixed

        modules = [g["module"] for adapter in sections(out, "graph").values() for g in adapter["items"] if g["kind"] == "module"]

        assert len(modules) == len(set(modules))
        assert any("/" in m for m in modules) and any("." in m for m in modules)

    def test_every_candidate_has_a_unique_id(self, mixed):
        _, out, _ = mixed
        extract = candidates.load(out)

        for output in candidates.ID_OUTPUTS:
            ids = [i["id"] for i in extract.get(output, []) if "id" in i]
            assert len(ids) == len(set(ids)), output

    def test_the_components_report_lists_python_packages_and_javascript_projects(self, mixed):
        _, out, tree = mixed

        text = candidates.text("components", candidates.load(out), {}, {}, tree=set(tree))

        assert "== Python packages ==" in text and "== JavaScript and TypeScript projects ==" in text
