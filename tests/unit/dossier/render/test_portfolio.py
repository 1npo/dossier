import json
from datetime import datetime, timezone

from dossier.render import portfolio

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


def test_card_has_header_region_and_body_with_langs(tmp_path):
    make(tmp_path, "a")
    text = portfolio.write(tmp_path, "1.5.0").read_text()
    assert '<header class="dhead">' in text and 'class="dstats"' in text and 'class="desc"' in text
    assert 'class="card dcard"' in text and '<div class="bar"' not in text.split('class="dhead"')[1].split("</header>")[0]


def test_stamp_uses_12_hour_clock_and_falls_back_to_date():
    import re
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} (AM|PM)", portfolio.stamp("2026-11-11T02:56:46Z"))
    assert portfolio.stamp("2026-11-11") == "2026-11-11"


def test_title_favicon_and_separate_git_pills(tmp_path):
    d = tmp_path / "a"; d.mkdir(); (d / "dossier-a.html").write_text("<html></html>")
    (d / "summary.json").write_text('{"repo": {"name": "a", "branch": "main", "sha": "5923c09081abc", "commit_date": "2026-10-24T10:00:00Z"}}')
    text = portfolio.write(tmp_path, "1.6.5").read_text()
    assert "<title>dossier portfolio</title>" in text and 'rel="icon"' in text
    assert 'data-variant="outline">main</span><span class="badge" data-variant="outline">5923c09081</span>' in text and "2026-10-24" not in text


def test_card_puts_last_built_before_the_git_pills(tmp_path):
    make(tmp_path, "a")
    card = portfolio.write(tmp_path, "1.5.0").read_text().split('<a class="card dcard"', 1)[1]
    assert card.index("<h2>a</h2>") < card.index("Last built") < card.index(">main</span>")
    assert 'Last built' in card.split('</div>', 2)[1] and 'data-variant="outline">main' not in card.split('</div>', 2)[1]


def test_keybinds_button_panel_and_selection_keys(tmp_path):
    make(tmp_path, "a")
    text = portfolio.write(tmp_path, "1.5.0").read_text()
    assert text.index('id="theme-toggle"') < text.index('id="keys-btn"') < text.index('class="tools"')
    assert 'id="keys-panel" class="keys-panel shut"' in text and "translateX(100%)" in text
    assert 'id="keys-panel"' in text and "Open the selected dossier." in text
    assert "ArrowDown" in text and 'e.key === "Enter"' in text


def test_last_built_pill_stays_inside_chips_so_it_gets_the_outline_stroke(tmp_path):
    make(tmp_path, "a")
    text = portfolio.write(tmp_path, "1.5.0").read_text()
    assert '<span class="chips"><span class="badge" data-variant="outline">Last built' in text


def test_card_body_children_have_no_extra_margins(tmp_path):
    make(tmp_path, "a")
    assert ".dcard .langs { margin: 0; }" in portfolio.write(tmp_path, "1.5.0").read_text()


def test_keys_button_is_level_with_the_title_and_the_last_built_pill_is_under_it(tmp_path):
    make(tmp_path, "a")
    text = portfolio.write(tmp_path, "1.5.0").read_text()
    header, rest = text.split("</header>", 1)
    assert "Last built" not in header and 'id="keys-btn"' not in header
    hero = rest.split('<section class="hero">', 1)[1].split("</section>", 1)[0]
    head = hero.split("</div>", 1)[0]
    assert "<h1>Your dossiers</h1>" in head and 'id="keys-btn"' in head
    assert hero.index('id="keys-btn"') < hero.index("Last built") < hero.index('class="summary"')

