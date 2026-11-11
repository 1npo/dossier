import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import summary

SKILL = Path(__file__).resolve().parents[3]
FIXTURE = SKILL / "tests" / "fixtures" / "encamp-m0"
REPO = Path(os.environ.get("DOSSIER_SUBJECT_REPO", SKILL.parent / "encamp"))  # the repository the frozen fixture was made from; only read when the fixture exists
pytestmark = pytest.mark.skipif(not FIXTURE.exists(), reason="the frozen fixture is not in this checkout")


@pytest.fixture
def render(tmp_path):
    shutil.copytree(FIXTURE, tmp_path / "home" / "encamp")
    (tmp_path / "home" / "encamp" / "dossier-encamp.html").unlink(missing_ok=True)
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), "DOSSIER_HOME": str(tmp_path / "home"), "DOSSIER_CONFIG": str(tmp_path / "cfg.json"),
           "DOSSIER_CACHE": str(tmp_path / "cache"), "PYTHONDONTWRITEBYTECODE": "1"}

    def run(command, *args):
        return subprocess.run([sys.executable, str(SKILL / "scripts" / "dossier.py"), command, str(REPO), *args], capture_output=True, text=True, env=env)

    run("migrate")
    run.out = tmp_path / "home" / "encamp"
    return run


class TestRenderWritesTheSummary:
    def test_allow_errors_writes_a_summary_that_validates(self, render):
        result = render("render", "--allow-errors")

        doc = json.loads((render.out / "summary.json").read_text())
        assert result.returncode == 0 and summary.validate(doc) == [] and "@" not in json.dumps(doc)
        assert doc["repo"]["name"] == "encamp" and doc["schema_version"] == 1
