"""The version lives in `VERSION` and `.claude-plugin/plugin.json`; they must agree, and the bump tool must keep them so."""
import json
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SKILL / "scripts"))
import bump_version  # noqa: E402


def test_plugin_manifest_version_matches_version_file():
    manifest = json.loads((SKILL / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["version"] == (SKILL / "VERSION").read_text().strip()


def test_marketplace_entry_names_the_plugin_and_points_at_the_root():
    plugin = json.loads((SKILL / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((SKILL / ".claude-plugin" / "marketplace.json").read_text())
    (entry,) = market["plugins"]
    assert entry["name"] == plugin["name"] == "dossier"
    assert entry["source"] == "./"


@pytest.mark.parametrize(
    "current, how, expected",
    [("1.0.0", "minor", "1.1.0"), ("1.4.3", "major", "2.0.0"), ("1.4.3", "patch", "1.4.4"), ("1.0.0", "2.5.1", "2.5.1")],
)
def test_bump(current, how, expected):
    assert bump_version.bump(current, how) == expected


@pytest.mark.parametrize("how", ["", "big", "1.2", "v1.2.3"])
def test_bump_rejects_bad_argument(how):
    with pytest.raises(ValueError):
        bump_version.bump("1.0.0", how)
