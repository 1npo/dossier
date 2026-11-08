import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SKILL / "tests" / "tools"))

import skeleton  # noqa: E402


def card(cid, title, tier):
    return (f'<div class="card block fact" id="c-{cid}" data-card="{cid}"><header><h3>{title}</h3><div class="card-badges">'
            f'<span class="badge tier tier-{tier.lower()}" data-variant="outline" tabindex="0">{tier}</span></div></header><section>x</section></div>')


def page(*cards, report="reading"):
    return f'<main><section class="report" id="{report}" hidden>{"".join(cards)}</section><footer class="foot"></footer></main>'


A = page(card("reading.map", "Where things live", "M"), card("reading.order", "Reading order", "B"))


def write(tmp_path, name, text):
    f = tmp_path / name
    f.write_text(text)
    return str(f)


class TestSkeleton:
    def test_it_lists_each_card_with_its_report_title_and_tier_in_page_order(self):
        assert skeleton.skeleton(A) == [("reading", "reading.map", "Where things live", "M"), ("reading", "reading.order", "Reading order", "B")]

    def test_a_title_is_unescaped(self):
        assert skeleton.skeleton(page(card("a.b", "Cats &amp; dogs", "A")))[0][2] == "Cats & dogs"

    def test_pages_with_the_same_cards_match_whatever_is_inside_them(self, tmp_path, capsys):
        b = A.replace("<section>x</section>", "<section>Very different content</section>")

        assert skeleton.main([write(tmp_path, "a.html", A), write(tmp_path, "b.html", b)]) == 0
        assert "DIFFERENT" not in capsys.readouterr().out

    def test_a_missing_card_is_named_and_the_exit_code_is_1(self, tmp_path, capsys):
        b = page(card("reading.map", "Where things live", "M"))

        assert skeleton.main([write(tmp_path, "a.html", A), write(tmp_path, "b.html", b)]) == 1
        assert "missing: ('reading', 'reading.order', 'Reading order', 'B')" in capsys.readouterr().out

    def test_a_changed_tier_is_a_difference(self, tmp_path, capsys):
        b = A.replace(">B</span>", ">A</span>")

        assert skeleton.main([write(tmp_path, "a.html", A), write(tmp_path, "b.html", b)]) == 1
        out = capsys.readouterr().out
        assert "extra:" in out and "missing:" in out

    def test_a_reordered_page_is_a_difference(self, tmp_path, capsys):
        b = page(card("reading.order", "Reading order", "B"), card("reading.map", "Where things live", "M"))

        assert skeleton.main([write(tmp_path, "a.html", A), write(tmp_path, "b.html", b)]) == 1
        assert "different order" in capsys.readouterr().out

    def test_no_pages_is_a_usage_error(self):
        assert skeleton.main([]) == 2
