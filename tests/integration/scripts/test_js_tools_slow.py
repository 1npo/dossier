import functools
import os
import subprocess
from pathlib import Path

import pytest

import js_tools
import sandbox
import toolcheck

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")


def test_real_install_gives_the_pinned_knip_and_a_working_node_gate(tmp_path):
    area = tmp_path / "cache" / "repo"
    area.mkdir(parents=True)
    run = functools.partial(sandbox.run, area=area, cwd=tmp_path, timeout=900)

    folder = js_tools.ensure_installed(run, area.parent, 900)

    out = subprocess.run(["node", str(folder / "node_modules/knip/bin/knip.js"), "--version"], capture_output=True, text=True)
    pinned = next(t["version"] for t in toolcheck.load_tools()["tools"] if t["id"] == "knip")
    assert out.stdout.strip() == pinned
    assert (folder / "ts_facts.mjs").exists()
    assert js_tools.node_problem(run) is None
