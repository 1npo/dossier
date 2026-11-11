import json
from datetime import datetime, timezone

import portfolio

NOW = datetime(2026, 1, 10, tzinfo=timezone.utc)


def make(home, name, built="2026-01-01T00:00:00Z", version="1.5.0"):
    d = home / name
    d.mkdir()
    (d / f"dossier-{name}.html").write_text("<html></html>")
    (d / "summary.json").write_text(json.dumps({
        "dossier_version": version, "generated_at": built,
        "repo": {"name": name, "branch": "main", "sha": "a" * 40, "commit_date": "2026-01-01"},
        "languages": [{"name": "Python", "share": 100}], "components": [{}, {}], "entry_points": [{}],
        "risks": {"high": 1}, "gaps": {"inference": 3, "unknown": 1}}))
    return d


def test_lists_only_built_dossiers_newest_first(tmp_path):
    make(tmp_path, "old", "2025-12-01T00:00:00Z")
    make(tmp_path, "new")
    (tmp_path / "scratch").mkdir()
    items = portfolio.collect(tmp_path, "1.5.0", NOW)
    assert [i["name"] for i in items] == ["new", "old"]
    assert items[0]["page"] == "new/dossier-new.html" and items[0]["age_days"] == 9


def test_page_links_each_dossier_and_flags_old_skill(tmp_path):
    make(tmp_path, "a", version="1.0.0")
    path = portfolio.write(tmp_path, "1.5.0")
    text = path.read_text()
    assert path.name == "index.html" and 'href="a/dossier-a.html"' in text and "older skill" in text
    assert not list(tmp_path.glob("*.tmp"))


def test_empty_home_still_writes_a_page(tmp_path):
    assert "No dossiers yet" in portfolio.write(tmp_path, "1.5.0").read_text()


def test_header_pill_brand_version_and_search_hint(tmp_path):
    make(tmp_path, "a")
    text = portfolio.write(tmp_path, "1.5.0").read_text()
    assert 'data-variant="outline">Last built ' in text and 'class="brand-ver">v1.5.0' in text
    assert '<kbd id="search-hint">/</kbd>' in text and "press /" not in text
    assert "Cited, commit-pinned" not in text and 'e.key === "t"' in text
