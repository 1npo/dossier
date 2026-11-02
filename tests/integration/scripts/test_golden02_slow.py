import os
from pathlib import Path

import pytest
from test_check_page_slow import rendered_page, run  # noqa: F401  (the fixture renders the frozen fixture once)

import broken_pages

SKILL = Path(__file__).resolve().parents[3]
GOLDEN = SKILL / "tests" / "tools" / "golden02.py"
BASELINES = SKILL / "tests" / "fixtures" / "golden02"

pytestmark = [
    pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs a browser: set DOSSIER_SLOW=1"),
    pytest.mark.skipif(not (BASELINES / "facts-git-light.png").exists(),
                       reason="no baselines in tests/fixtures/golden02: make them as that folder's README says"),
]


def compare(page, env, tmp_path):
    return run(GOLDEN, page, BASELINES, "--diff-dir", tmp_path / "now", env=env)


class TestReport02Golden:
    def test_the_page_the_current_code_renders_looks_as_the_pre_m0_page_did(self, rendered_page, tmp_path):  # noqa: F811
        page, env = rendered_page

        done = compare(page, env, tmp_path)

        assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-500:]

    def test_a_page_with_a_conflict_in_its_stylesheet_does_not_match(self, rendered_page, tmp_path):  # noqa: F811
        page, env = rendered_page
        broken = tmp_path / "broken.html"
        broken.write_text(broken_pages.mutate(page.read_text(), "conflict-css"))

        done = compare(broken, env, tmp_path)

        assert done.returncode == 1 and "FAIL" in done.stdout

    def test_one_changed_css_rule_of_report_02_does_not_match(self, rendered_page, tmp_path):  # noqa: F811
        page, env = rendered_page
        changed = tmp_path / "changed.html"
        changed.write_text(broken_pages.mutate(page.read_text(), "km-row-taller"))

        done = compare(changed, env, tmp_path)

        assert done.returncode == 1 and "facts-contributors" in done.stdout
