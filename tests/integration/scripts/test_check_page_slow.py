import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SKILL / "tests" / "tools"))

import broken_pages  # noqa: E402

FIX = SKILL / "tests" / "fixtures" / "encamp-m0"
TOP = SKILL.parents[5]
CHECK = SKILL / "scripts" / "check_page.py"

pytestmark = [
    pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs a browser: set DOSSIER_SLOW=1"),
    pytest.mark.skipif(not FIX.exists(), reason="the frozen fixture tests/fixtures/encamp-m0 is absent"),
]


def run(*args, env, cwd=SKILL):
    return subprocess.run(["uv", "run", *map(str, args)], capture_output=True, text=True, env=env, cwd=cwd)


@pytest.fixture(scope="module")
def rendered_page(tmp_path_factory):
    """The migrated M0 fixture, rendered once for the whole module."""
    base = tmp_path_factory.mktemp("page")
    home = base / "home"
    shutil.copytree(FIX, home / "encamp")
    for p in (home / "encamp").rglob("*"):
        p.chmod(p.stat().st_mode | 0o200)
    (home / "encamp" / "dossier-encamp.html").unlink(missing_ok=True)
    env = {**os.environ, "DOSSIER_HOME": str(home), "DOSSIER_CONFIG": str(base / "cfg.json"), "DOSSIER_CACHE": str(base / "cache")}
    assert run(SKILL / "scripts" / "dossier.py", "migrate", TOP, env=env).returncode == 0
    done = run(SKILL / "scripts" / "dossier.py", "render", TOP, "--allow-errors", env=env)
    assert done.returncode == 0, done.stdout[-500:] + done.stderr[-500:]
    return home / "encamp" / "dossier-encamp.html", env


def check(path, env):
    return run(CHECK, path, env=env)


class TestCheckPageOnBrokenPages:
    def test_unmutated_page_passes(self, rendered_page):
        page, env = rendered_page

        done = check(page, env)

        assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]

    def test_conflict_marker_in_stylesheet_is_reported_not_a_traceback(self, rendered_page, tmp_path):
        page, env = rendered_page
        broken = tmp_path / "broken.html"
        broken.write_text(broken_pages.mutate(page.read_text(), "conflict-css"))

        done = check(broken, env)

        assert done.returncode == 1
        assert "stylesheet" in done.stdout
        assert "Traceback" not in done.stderr + done.stdout

    def test_missing_script_sentinel_is_reported(self, rendered_page, tmp_path):
        page, env = rendered_page
        broken = tmp_path / "broken.html"
        broken.write_text(broken_pages.mutate(page.read_text(), "no-js-sentinel"))

        done = check(broken, env)

        assert done.returncode == 1
        assert "script" in done.stdout
        assert "Traceback" not in done.stderr + done.stdout
