import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import PYFIX, _commit_fixture

SKILL = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    """PYFIX plus one Rust and one more shell file, built and rendered with the real CLI (M6-8)."""
    base = tmp_path_factory.mktemp("tierb")
    parts = base / "parts"
    shutil.copytree(PYFIX, parts, ignore=shutil.ignore_patterns("__pycache__", "node_modules"))
    (parts / "native").mkdir()
    (parts / "native" / "lib.rs").write_text("pub fn add(a: i32, b: i32) -> i32 { a + b }\n")
    (parts / "tools").mkdir()
    (parts / "tools" / "run.sh").write_text("#!/bin/sh\necho run\n")
    repo = _commit_fixture(parts, base, "tierb", chmod=[Path("scripts") / "seed.sh"])
    env = {**os.environ, "DOSSIER_HOME": str(base / "home"), "DOSSIER_CONFIG": str(base / "cfg.json"), "DOSSIER_CACHE": str(base / "cache"),
           "PYTHONDONTWRITEBYTECODE": "1"}

    def run(*args):
        return subprocess.run([sys.executable, str(SKILL / "scripts" / "dossier.py"), *args, repo.path], capture_output=True, text=True, env=env)

    prepared = run("prepare", "--no-restore")
    rendered = run("render", "--allow-errors", "--partial")
    html = next((base / "home" / "tierb").glob("dossier-*.html")).read_text(encoding="utf-8")
    return prepared, rendered, html


def test_the_eight_graph_cards_carry_the_badge_and_the_tip_names_the_languages(page):
    prepared, rendered, html = page

    assert prepared.returncode == 0 and rendered.returncode == 0, prepared.stderr + rendered.stderr
    assert html.count('class="badge nograph"') == 8
    tip = re.search(r'class="badge nograph"[^>]*data-tip="([^"]*)"', html).group(1)
    assert tip == "No import or call graph was made for Shell (2 files), Rust (1 file). Their files are in the tables but have no links."
