import functools
import os
import re
from pathlib import Path

import pytest

from dossier.adapters.csharp import semgrep as cs_semgrep
from dossier.tooling import sandbox
from dossier.tooling import shared_tools
from dossier import resources
from cs_slow import BLIND, IO
from paths import SKILL_ROOT

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")

ENTRY = {"ep-min-get": ("http-route", "GET /health"), "ep-min-post": ("http-route", "POST /orders"), "ep-hub": ("signalr-hub", "/chat"),
         "ep-grpc": ("grpc-service", "Greeter"), "ep-hosted-add": ("hosted-service", "Cleanup"), "ep-cron": ("scheduled-job", "nightly"),
         "ep-target": ("build-target", "default"), "ep-cli": ("cli-command", "sync")}


@pytest.fixture(scope="module")
def found(tmp_path_factory, request):
    from repos import build_cs_repo
    root = tmp_path_factory.mktemp("cssemgrep")
    repo = build_cs_repo(root)
    area = root / "cache" / "repo"
    area.mkdir(parents=True)
    run = functools.partial(sandbox.run, area=area, cwd=Path(repo.path), timeout=900)
    files = sorted(str(p.relative_to(repo.path)) for p in Path(repo.path).rglob("*.cs"))
    results = shared_tools.Semgrep(run).scan(resources.data("rules"), [f for f in files if not f.endswith(".Designer.cs")], timeout=120)
    owner = lambda p: "build/build.csproj" if p.startswith("build/") else None  # noqa: E731
    marks = {}
    for f in files:
        for n, line in enumerate((Path(repo.path) / f).read_text().splitlines(), 1):
            for m in re.findall(r"@([a-z0-9-]+)", line):
                marks.setdefault(m, []).append((f, n))
    return cs_semgrep.items([r for r in results if ".csharp." in r["rule"]], owner, {"build/build.csproj"}), marks


def _covering(rows, path, line):
    return [r for r in rows if r["path"] == path and r["line"] <= line <= r["end_line"]]


class TestFixtureMarkers:
    @pytest.mark.parametrize("marker,category", sorted(IO.items()))
    def test_every_io_marker_has_a_finding_of_its_category(self, found, marker, category):
        items, marks = found

        assert marks[marker], marker
        for path, line in marks[marker]:
            assert category in {r["category"] for r in _covering(items["io_candidates"], path, line)}, (marker, path, line)

    @pytest.mark.parametrize("marker,expected", sorted(ENTRY.items()))
    def test_every_entry_marker_has_its_entry_point(self, found, marker, expected):
        items, marks = found

        for path, line in marks[marker]:
            assert expected in {(e["kind"], e["name"]) for e in _covering(items["entry_points"], path, line)}, (marker, path, line)

    def test_near_misses_give_no_entry_point(self, found):
        items, marks = found

        for path, line in marks["not-route"]:
            assert not _covering(items["entry_points"], path, line)


    @pytest.mark.parametrize("marker,pattern", sorted(BLIND.items()))
    def test_every_blind_spot_marker_has_its_pattern(self, found, marker, pattern):
        items, marks = found

        assert marks[marker], marker
        for path, line in marks[marker]:
            assert pattern in {b["pattern"] for b in _covering(items["blindspots"], path, line)}, (marker, path, line)
