"""The environment-variable and secret-signal cards on a built page (post-v1 items 17 and 18)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from repos import build_py_repo
from paths import LAUNCHER

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="runs the extractors: set DOSSIER_SLOW=1")

FAKE_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"
FAKE_GH = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    base = tmp_path_factory.mktemp("envcards")
    repo = Path(build_py_repo(base).path)
    (repo / "src" / "leaky.py").write_text(f'KEY = "{FAKE_AWS}"\nTOKEN = "{FAKE_GH}"\n')
    (repo / "src" / "cfg_env.py").write_text('import os\nPORT = os.environ.get("APP_PORT", "8080")\n')
    (repo / ".env").write_text("APP_PORT=1\n")
    for args in (["add", "-A"], ["-c", "user.name=T", "-c", "user.email=t@x.io", "commit", "-qm", "plant"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    env = {**os.environ, "DOSSIER_HOME": str(base / "home"), "DOSSIER_CONFIG": str(base / "cfg.json"), "DOSSIER_CACHE": str(base / "cache")}
    for step in (["prepare", str(repo)], ["render", str(repo), "--partial", "--allow-errors"]):
        subprocess.run([sys.executable, str(LAUNCHER), *step], check=True, capture_output=True, env=env)
    out = base / "home" / repo.name
    return out, (out / f"dossier-{repo.name}.html").read_text()


def card(page, cid):
    i = page.index(f'data-card="{cid}"')
    return page[i:page.index("</section>", i)]


class TestPlantedSecret:
    def test_no_value_is_in_the_page_or_in_the_saved_files(self, built):
        out, page = built

        assert FAKE_AWS not in page and FAKE_GH not in page
        for f in out.rglob("*"):
            if f.is_file():
                text = f.read_text(errors="ignore")
                assert FAKE_AWS not in text and FAKE_GH not in text, f

    def test_the_card_lists_the_matches_by_path_line_and_pattern(self, built):
        _, page = built
        body = card(page, "ops.secret-signals")

        assert "not a security scanner" in body
        assert "aws-access-key-id" in body and "github-token" in body and "leaky.py" in body
        assert 'id="t-ops-secret-signals"' in body


class TestEnvCard:
    def test_it_lists_every_variable_with_its_default_and_declaration(self, built):
        _, page = built
        body = card(page, "ops.env-vars")

        assert "APP_PORT" in body and "8080" in body and ".env" in body and "SHOP_DB" in body

    def test_check_finds_nothing_wrong_with_either_card(self, built, tmp_path):
        out, _ = built
        facts = json.loads((out / "facts.json").read_text())
        r = subprocess.run([sys.executable, str(LAUNCHER), "check", facts["repo"]["path"]], capture_output=True, text=True,
                           env={**os.environ, "DOSSIER_HOME": str(out.parent), "DOSSIER_CONFIG": str(tmp_path / "c.json"), "DOSSIER_CACHE": str(tmp_path / "k")})

        assert "ops.env-vars" not in r.stdout and "ops.secret-signals" not in r.stdout
