import functools
import os
import re
from pathlib import Path

import pytest

import cs_semgrep
import sandbox
import shared_tools

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")

SKILL = Path(__file__).resolve().parents[3]
IO = {"io-args": "cli-args", "io-config": "config-file", "io-connstr": "config-file", "io-dapper": "db-access", "io-db": "db-access", "io-db-connect": "db-connect",
      "io-db-save": "db-access", "io-env": "env-var", "io-error": "error-response", "io-exit": "exit-code", "io-file-read": "file-read", "io-file-write": "file-write",
      "io-header": "request-header", "io-log": "log", "io-log2": "log", "io-outbound": "outbound-call", "io-outbound-add": "outbound-call", "io-produce": "message-produce",
      "io-stdin": "stdin", "io-stdout": "stdout", "fail-catch": "catch-all", "fail-handler": "catch-all", "fail-retry": "retry", "fail-tx": "transaction",
      "cc-lock": "lock", "cc-async": "async"}
ENTRY = {"ep-min-get": ("http-route", "GET /health"), "ep-min-post": ("http-route", "POST /orders"), "ep-hub": ("signalr-hub", "/chat"),
         "ep-grpc": ("grpc-service", "Greeter"), "ep-hosted-add": ("hosted-service", "Cleanup"), "ep-cron": ("scheduled-job", "nightly"),
         "ep-target": ("build-target", "default"), "ep-cli": ("cli-command", "sync")}


BLIND = {"bs-di": "di-registration", "bs-scan": "di-scan", "bs-convention": "route-convention", "bs-convention-class": "route-convention", "bs-filter": "mvc-filter",
         "bs-filter-class": "mvc-filter", "bs-group": "route-mount", "bs-route": "string-route", "bs-conventional": "conventional-route",
         "bs-mediator-send": "mediator-handler", "bs-handler": "mediator-handler", "bs-resolve": "di-resolution", "bs-reflect": "reflection",
         "bs-flag": "feature-flag", "bs-generator": "source-generator", "bs-partial": "partial-class"}


@pytest.fixture(scope="module")
def found(tmp_path_factory, request):
    from conftest import build_cs_repo
    root = tmp_path_factory.mktemp("cssemgrep")
    repo = build_cs_repo(root)
    area = root / "cache" / "repo"
    area.mkdir(parents=True)
    run = functools.partial(sandbox.run, area=area, cwd=Path(repo.path), timeout=900)
    files = sorted(str(p.relative_to(repo.path)) for p in Path(repo.path).rglob("*.cs"))
    results = shared_tools.Semgrep(run).scan(SKILL / "rules", [f for f in files if not f.endswith(".Designer.cs")], timeout=120)
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
