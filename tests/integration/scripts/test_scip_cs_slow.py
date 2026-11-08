import functools
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import cs_project
import cs_queries
import cs_scip
import cs_sdk
import sandbox
import scip_read
import shared_tools
import toolcheck
import workarea
from conftest import build_cs_repo

pytestmark = [
    pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1"),
    pytest.mark.skipif(shutil.which("dotnet") is None or "10.0.403" not in cs_sdk.list_sdks(),
                       reason="needs the .NET SDK 10.0.403 (dotnet is not installed or is another version)"),
]


@pytest.fixture(scope="module")
def indexed(tmp_path_factory):
    base = tmp_path_factory.mktemp("csscip")
    os.environ["DOSSIER_CACHE"] = str(base / "cache")
    repo = build_cs_repo(base)
    area = workarea.area_for("csrepo", repo.path, repo.sha, base / "cache")
    checkout = Path(workarea.ensure_checkout(area, repo.path, repo.sha)["path"])
    run = functools.partial(sandbox.run, area=area, timeout=900)
    restore = run(["dotnet", "restore", "Shop.Core.csproj", "--locked-mode", "-p:NuGetAudit=false"], cwd=checkout / "src/Shop.Core", stage="restore-nuget",
                  ecosystem="nuget")
    assert restore.returncode == 0, restore.stderr.read_text()
    tool = next(t for t in toolcheck.load_tools()["tools"] if t["id"] == "scip-dotnet")
    dll = cs_scip.tool_dll(cs_scip.ensure_installed(area.parent, tool, 900), cs_sdk.list_runtime_majors())
    path, code, log = cs_scip.ScipDotnet(functools.partial(run, ecosystem="nuget"), dll, 900).index(checkout, "Shop.slnx", area, 0)
    tracked = frozenset(subprocess.run(["git", "-C", str(checkout), "ls-files"], capture_output=True, text=True).stdout.split())
    yield checkout, path, code, log, tracked
    shutil.rmtree(base, ignore_errors=True)
    os.environ.pop("DOSSIER_CACHE", None)


def _reduced(indexed):
    checkout, path, _, _, tracked = indexed
    files = sorted(f for f in tracked if f.endswith(".cs"))
    ts = shared_tools.TreeSitter(functools.partial(sandbox.run, area=path.parent.parent, cwd=checkout, timeout=600))
    decls = cs_queries.declarations(ts, files)
    index = cs_scip.join([scip_read.decode(path.read_bytes())], tracked)
    index, count = cs_scip.disambiguate(index, decls)
    return scip_read.reduce(index), count, decls


class TestShopSolution:
    def test_run_succeeded_and_wrote_an_index_outside_the_checkout(self, indexed):
        checkout, path, code, log, _ = indexed

        assert cs_scip.failure(code, log, path) is None and not list(checkout.rglob("*.scip"))

    def test_references_inside_the_restored_project_are_found(self, indexed):
        items, _, _ = _reduced(indexed)

        edges = {(i["path"], i["paths"][0]) for i in items if i["kind"] == "ref-edge"}

        assert ("src/Shop.Core/Order.cs", "src/Shop.Core/Customer.cs") in edges

    @pytest.mark.xfail(strict=True, reason="Only Shop.Core can be restored offline, and an unrestored project does not resolve its project references; "
                                           "Plan 011 M5-16 step 2 asks for this edge, which the fixture cannot give (see Results, Phase 3).")
    def test_api_references_core(self, indexed):
        items, _, _ = _reduced(indexed)

        assert any(i["kind"] == "ref-edge" and i["path"].startswith("src/Shop.Api/") and i["paths"][0].startswith("src/Shop.Core/") for i in items)

    def test_the_two_item_classes_are_counted_as_ambiguous(self, indexed):
        _, count, _ = _reduced(indexed)

        assert count >= 1

    def test_checkout_has_no_tracked_change(self, indexed):
        checkout = indexed[0]

        status = subprocess.run(["git", "-C", str(checkout), "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True).stdout

        assert status == ""
