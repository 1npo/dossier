"""The module-level fixtures of the JavaScript adapter's slow tests, shared by the tests that reuse its extraction."""
import pytest
from types import SimpleNamespace

from dossier.core import buildlog
from dossier.pipeline import stages
from dossier.pipeline import workarea
from repos import build_js_repo

LANGS = ["TypeScript", "JavaScript", "JSON"]
def _extract(repo, out, area, checkout, trusted, tag):
    build = buildlog.start(out, repo="jsrepo", sha=repo.sha, ref="main", version=tag, options={})
    return stages.stage_extract(build, repo.path, repo.sha, area, out, LANGS, trusted, stages.Options(no_restore=True), {},
                                stages.tree_at(repo.path, repo.sha), checkout)


def _build(base_dir, trusted):
    patch = pytest.MonkeyPatch()
    patch.setenv("DOSSIER_HOME", str(base_dir / "home"))
    patch.setenv("DOSSIER_CONFIG", str(base_dir / "cfg.json"))
    patch.setenv("DOSSIER_CACHE", str(base_dir / "cache"))
    repo = build_js_repo(base_dir)
    out = base_dir / "home" / "jsrepo"
    area = workarea.area_for("jsrepo", repo.path, repo.sha, base_dir / "cache")
    checkout = workarea.ensure_checkout(area, repo.path, repo.sha)["path"]
    record = _extract(repo, out, area, checkout, trusted(repo) if callable(trusted) else trusted, "test")
    return patch, SimpleNamespace(repo=repo, out=out, record=record, area=area, checkout=checkout, trusted=trusted)


@pytest.fixture(scope="module")
def extraction(tmp_path_factory):
    """One extraction of the JavaScript fixture repository with every tool."""
    patch, got = _build(tmp_path_factory.mktemp("jsadapter"), lambda repo: workarea.trusted(repo.path, repo.sha))
    try:
        yield got
    finally:
        patch.undo()


@pytest.fixture(scope="module")
def ex(extraction):
    return extraction.repo, extraction.out, extraction.record
