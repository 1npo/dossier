import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import report_section as rs  # noqa: E402

PAGE = (
    '<section class="report" id="a" hidden><p>one</p></section>'
    '<section class="report" id="b" hidden><h1>B</h1><p class="question">Q?</p>'
    '<div class="card" id="x" data-card="b.one"><header><h3>T</h3>'
    '<span class="badge tier tier-a" data-tip="t">A</span></header></div>'
    '<p class="tier-key">key</p><p>kept</p></section>'
    '<section class="report" id="c" hidden><p>three</p></section>'
    '<footer class="foot">f</footer>'
)


def test_section_returns_the_middle_one():
    s = rs.section(PAGE, "b")
    assert s.startswith('<section class="report" id="b"') and s.endswith("</section>") and "<p>one</p>" not in s and "three" not in s


def test_last_section_stops_before_footer():
    assert rs.section(PAGE, "c").endswith("three</p></section>")


def test_missing_report_exits():
    with pytest.raises(SystemExit):
        rs.section(PAGE, "zzz")


def test_normalize_removes_only_the_additions():
    n = rs.normalize(rs.section(PAGE, "b"))
    assert "data-card" not in n and "badge" not in n and "question" not in n and "tier-key" not in n
    assert "<h1>B</h1>" in n and "<h3>T</h3>" in n and "<p>kept</p>" in n


def test_normalize_is_identity_without_additions():
    s = rs.section(PAGE, "a")
    assert rs.normalize(s) == s


def test_cards_per_report():
    assert rs.cards(PAGE) == {"a": [], "b": ["b.one"], "c": []}


def test_cli_digest(tmp_path, capsys):
    p = tmp_path / "p.html"
    p.write_text(PAGE, encoding="utf-8")
    rs.main([str(p), "a", "--digest"])
    s = rs.section(PAGE, "a")
    assert capsys.readouterr().out.split() == [hashlib.sha256(s.encode()).hexdigest(), str(len(s))]
    rs.main([str(p), "--cards"])
    assert json.loads(capsys.readouterr().out)["b"] == ["b.one"]
