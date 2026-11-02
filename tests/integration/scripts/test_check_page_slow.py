import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SKILL / "tests" / "tools"))

import broken_pages  # noqa: E402

sys.path.insert(0, str(SKILL / "scripts"))

import measured_er  # noqa: E402

FIX = SKILL / "tests" / "fixtures" / "encamp-m0"
TOP = SKILL.parents[5]
CHECK = SKILL / "scripts" / "check_page.py"
DIAGRAM_TEXT = SKILL / "tests" / "tools" / "diagram_text.py"
TABLE_FIT = SKILL / "tests" / "tools" / "table_fit.py"

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


class TestDiagramText:
    @pytest.fixture(scope="class")
    def sizes(self, rendered_page, tmp_path_factory):
        page, env = rendered_page
        big = tmp_path_factory.mktemp("big") / "big.html"
        big.write_text(broken_pages.mutate(page.read_text(), "big-diagrams"))
        done = run(DIAGRAM_TEXT, big, env=env)
        assert done.returncode == 0, done.stderr[-800:]
        return [r for r in json.loads(done.stdout) if r["title"].startswith("Injected")]

    @pytest.mark.parametrize("width", [1500, 400])
    def test_text_in_a_wide_diagram_is_at_least_11px(self, sizes, width):
        rows = [r for r in sizes if r["width"] == width]

        assert len(rows) == 2
        assert all(r["min_height"] >= 11 for r in rows), rows


class TestTablesFitTheCard:
    @pytest.fixture(scope="class")
    def fit(self, rendered_page, tmp_path_factory):
        page, env = rendered_page
        wide = tmp_path_factory.mktemp("wide") / "wide.html"
        wide.write_text(broken_pages.mutate(page.read_text(), "wide-tables"))
        done = run(TABLE_FIT, wide, env=env)
        assert done.returncode == 0, done.stderr[-800:]
        return {(r["width"], r["id"]): r for r in json.loads(done.stdout)}

    def test_seven_column_table_does_not_scroll_at_desktop_width(self, fit):
        row = fit[(1500, "inj-7")]

        assert row["scrollWidth"] <= row["clientWidth"], row
        assert not row["scrolls_class"] and not row["hint"]

    def test_nine_column_table_at_phone_width_says_it_scrolls(self, fit):
        row = fit[(400, "inj-9")]

        assert row["scrollWidth"] > row["clientWidth"]
        assert row["scrolls_class"] and row["hint"]


class TestRelationshipDiagramsDraw:
    def entity(self, name, fields, kind="dataclass", path="src/app/m.py"):
        return {"path": path, "line": 1, "name": name, "kind": kind, "fields": [{"name": n, "type": t, "line": 2, "ref": r, **({"pk": True} if pk else {})} for n, t, r, pk in fields]}

    def test_every_generated_er_diagram_is_accepted_by_mermaid(self, rendered_page, tmp_path):
        page, env = rendered_page
        models = [
            self.entity("Alert", [("product", "Product", "Product", False), ("limits", "Mapping[str, float]", None, False),
                                  ("when", "datetime | None", None, False), ("steps", "tuple[Alert, ...]", "Alert", False),
                                  ("cb", "Callable[[int], str]", None, False), ("nested", "dict[str, list[int]]", None, False)]),
            self.entity("Product", [("id", "INTEGER", None, True), ("1st", "str", None, False), ("odd name!", "str", None, False)]),
            self.entity("runs", [("id", "INTEGER", None, True)], kind="sql-table", path="db/schema.sql"),
            self.entity("scrapes", [("id", "INTEGER", None, True), ("run_id", "INTEGER", "runs", False)], kind="sql-table", path="db/schema.sql"),
            self.entity("Empty", []),
        ]
        shown = measured_er.diagrams({"models": models, "graph": []}, [])
        broken = tmp_path / "er.html"
        broken.write_text(broken_pages.inject_diagrams(page.read_text(), [("Injected " + t, src) for t, src, _ in shown]))

        done = run(DIAGRAM_TEXT, broken, "--widths", "1500", env=env)

        rows = [r for r in json.loads(done.stdout) if r["title"].startswith("Injected")]
        assert len(rows) == len(shown) >= 1
        assert not [r for r in rows if r["failed"]], rows
