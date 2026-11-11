import functools
import os
from pathlib import Path

import pytest

from dossier.tooling import sandbox
from dossier.tooling import shared_tools
import tier_b

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tierb"
EXPECTED = {
    "Shell": ("deploy.sh", [(5, "build", "function"), (10, "deploy", "function"), (14, "rollback", "function")]),
    "Rust": ("lib.rs", [(2, "net", "module"), (6, "Config", "struct"), (10, "Mode", "enum"), (15, "Runner", "trait"), (19, "Alias", "type"), (25, "main", "function")]),
    "Go": ("server.go", [(4, "Server", "type"), (6, "Handler", "type"), (11, "ID", "type"), (12, "Name", "type"), (15, "New", "function"),
                         (17, "Start", "method"), (19, "helper", "function")]),
    "Ruby": ("app.rb", [(2, "Billing", "module"), (8, "Account", "class"), (14, "top_level_helper", "function")]),
    "Java": ("Shop.java", [(4, "Shop", "class"), (12, "Cart", "interface"), (16, "Status", "enum"), (18, "Item", "record")]),
}


@pytest.fixture(scope="module")
def ts(tmp_path_factory):
    area = tmp_path_factory.mktemp("tierb") / "cache" / "repo"
    area.mkdir(parents=True)
    return shared_tools.TreeSitter(functools.partial(sandbox.run, area=area, cwd=FIXTURES, timeout=600))


@pytest.mark.parametrize("language", sorted(EXPECTED))
def test_top_level_definitions_of_the_fixture(ts, language):
    name, want = EXPECTED[language]

    got = tier_b.symbols(ts, language, [name])

    assert [(s["line"], s["name"], s["symbol_kind"]) for s in got] == want


def test_the_fixture_covers_every_language_in_the_table():
    assert set(EXPECTED) == set(tier_b.LANGUAGES)
