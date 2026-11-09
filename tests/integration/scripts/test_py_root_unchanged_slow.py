import json
import os
from pathlib import Path

import pytest

from conftest import build_py_repo
from test_py_adapter_slow import Extracted

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")

SNAPSHOTS = Path(__file__).resolve().parents[2] / "fixtures" / "py_snapshot"
OUTPUTS = ("entry_points", "graph", "symbols", "io_candidates", "models", "tests", "dead", "blindspots")


@pytest.fixture(scope="module")
def ex(tmp_path_factory):
    base = tmp_path_factory.mktemp("pyroot")
    patch = pytest.MonkeyPatch()
    patch.setenv("DOSSIER_HOME", str(base / "home"))
    patch.setenv("DOSSIER_CONFIG", str(base / "cfg.json"))
    patch.setenv("DOSSIER_CACHE", str(base / "cache"))
    try:
        e = Extracted(base, build_py_repo(base))
        e.record = e.run()
        yield e
    finally:
        patch.undo()


def python_items(ex, output):
    data = json.loads((ex.out / "extract" / f"{output}.json").read_text())
    items = data["adapters"].get("python", {}).get("items", [])
    return json.loads(json.dumps(items).replace(ex.sha, "<sha>"))


class TestRootUnchanged:
    @pytest.mark.parametrize("output", OUTPUTS)
    def test_python_section_matches_the_snapshot(self, ex, output):
        path = SNAPSHOTS / f"{output}.json"
        got = python_items(ex, output)
        if not path.exists():
            SNAPSHOTS.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(got, indent=1, sort_keys=True) + "\n")

        assert got == json.loads(path.read_text())
