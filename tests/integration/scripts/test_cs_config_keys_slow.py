import functools
import os
from pathlib import Path

import pytest

import cs_semgrep
import measured_tables
import sandbox
import shared_tools

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "cscfg"


@pytest.fixture(scope="module")
def rows(tmp_path_factory):
    area = tmp_path_factory.mktemp("cscfg") / "repo"
    area.mkdir()
    run = functools.partial(sandbox.run, area=area, cwd=FIXTURE, timeout=900)
    results = shared_tools.Semgrep(run).scan(Path(__file__).resolve().parents[3] / "rules" / "csharp", ["Program.cs"], timeout=120)
    return cs_semgrep.items([r for r in results if ".csharp." in r["rule"]])["io_candidates"]


class TestConfigKeysOnTheFixture:
    def test_keys_and_options_classes_are_found_with_their_lines(self, rows):
        got = sorted((r["detail"], r["line"]) for r in rows if r["category"] == "config-key")

        assert got == [("Db", 7), ("Shop", 5), ("Shop:Name", 6), ("ShopOptions", 5), ("ShopOptions", 15)]

    def test_a_plain_dictionary_is_not_a_config_key(self, rows):
        assert 9 not in {r["line"] for r in rows if r["category"] == "config-key"}

    def test_no_row_holds_a_value(self, rows):
        assert "never-shown-secret-value" not in repr(rows)

    def test_the_inputs_group_lists_every_name_once_with_all_its_sites(self, rows):
        grouped = measured_tables.config_key_rows({"io_candidates": rows})

        assert [(n, k, [ln for _, ln in places]) for n, k, places in grouped] == [
            ("Db", "key", [7]), ("Shop", "key", [5]), ("Shop:Name", "key", [6]), ("ShopOptions", "options class", [5, 15])]
