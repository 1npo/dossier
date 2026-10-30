import json

import viewer


def numbered(n, width=10):
    return [f"line {i}".ljust(width) for i in range(1, n + 1)]


class TestSplitLines:
    def test_trailing_newline_adds_no_empty_line(self):
        assert viewer.split_lines(b"a\nb\n") == ["a", "b"]

    def test_missing_trailing_newline_keeps_last_line(self):
        assert viewer.split_lines(b"a\nb") == ["a", "b"]

    def test_crlf_endings_are_stripped(self):
        assert viewer.split_lines(b"a\r\nb\r\n") == ["a", "b"]

    def test_empty_file_has_no_lines(self):
        assert viewer.split_lines(b"") == []

    def test_blank_lines_in_the_middle_are_kept(self):
        assert viewer.split_lines(b"a\n\nb\n") == ["a", "", "b"]


class TestClip:
    def test_short_range_is_unchanged(self):
        assert viewer.clip(10, 20) == (10, 20)

    def test_range_over_the_cap_is_cut_to_its_first_lines(self):
        assert viewer.clip(10, 5000) == (10, 10 + viewer.MAX_LINES - 1)


class TestPickWindow:
    def test_small_file_is_embedded_whole(self):
        lines = numbered(100)

        window = viewer.pick_window(lines, [(5, 9), (90, 95)])

        assert window == (1, 100)

    def test_file_cited_without_line_numbers_starts_at_the_top(self):
        lines = numbered(3000)

        window = viewer.pick_window(lines, [None])

        assert window == (1, viewer.MAX_LINES)

    def test_long_file_uses_the_window_covering_the_most_ranges(self):
        lines = numbered(8000)

        window = viewer.pick_window(lines, [(10, 20), (5000, 5010), (5100, 5200), (5300, 5310)])

        assert window == (5000, 5000 + viewer.MAX_LINES - 1)

    def test_tie_goes_to_the_earliest_window(self):
        lines = numbered(8000)

        window = viewer.pick_window(lines, [(10, 20), (6000, 6010)])

        assert window == (1, viewer.MAX_LINES)

    def test_window_stops_at_the_end_of_the_file(self):
        lines = numbered(2000)

        window = viewer.pick_window(lines, [(1900, 1950), (1960, 1970)])

        assert window == (1900, 2000)

    def test_range_longer_than_the_cap_counts_as_its_first_lines(self):
        lines = numbered(8000)

        window = viewer.pick_window(lines, [(100, 7000), (3000, 3010)])

        assert window == (100, 100 + viewer.MAX_LINES - 1)

    def test_byte_cap_shrinks_the_window(self):
        lines = numbered(1500, width=200)

        first, last = viewer.pick_window(lines, [(1, 5)])

        assert first == 1
        assert last < 1500
        assert viewer.size_of(lines[first - 1:last]) <= viewer.MAX_BYTES
        assert viewer.size_of(lines[first - 1:last + 1]) > viewer.MAX_BYTES

    def test_multibyte_text_is_counted_in_bytes(self):
        lines = ["é" * 400 for _ in range(600)]

        first, last = viewer.pick_window(lines, [None])

        assert viewer.size_of(lines[first - 1:last]) <= viewer.MAX_BYTES
        assert last < 600


class TestCovers:
    def test_range_inside_the_window_is_covered(self):
        assert viewer.covers((100, 200), (120, 130))

    def test_range_outside_the_window_is_not_covered(self):
        assert not viewer.covers((100, 200), (150, 250))

    def test_citation_without_line_numbers_is_covered(self):
        assert viewer.covers((100, 200), None)

    def test_overlong_range_is_judged_by_its_clipped_part(self):
        assert viewer.covers((1, 1500), (1, 9000))


class TestPlan:
    def test_everything_under_budget_is_kept(self):
        files = {"a.py": {"lines": numbered(10), "ranges": [(1, 2)]}, "b.py": {"lines": numbered(10), "ranges": [None]}}

        windows, dropped = viewer.plan(files, budget=10_000)

        assert sorted(windows) == ["a.py", "b.py"]
        assert dropped == []

    def test_files_cited_without_line_numbers_are_dropped_first(self):
        files = {"numbered.py": {"lines": numbered(100), "ranges": [(1, 2)]},
                 "plain.py": {"lines": numbered(100), "ranges": [None]}}
        budget = viewer.size_of(numbered(100)) + 10

        windows, dropped = viewer.plan(files, budget=budget)

        assert dropped == ["plain.py"]
        assert list(windows) == ["numbered.py"]

    def test_then_the_files_with_the_fewest_citations_go(self):
        files = {"many.py": {"lines": numbered(100), "ranges": [(1, 2), (3, 4), (5, 6)]},
                 "one.py": {"lines": numbered(100), "ranges": [(1, 2)]},
                 "two.py": {"lines": numbered(100), "ranges": [(1, 2), (3, 4)]}}
        budget = 2 * viewer.size_of(numbered(100)) + 10

        windows, dropped = viewer.plan(files, budget=budget)

        assert dropped == ["one.py"]
        assert sorted(windows) == ["many.py", "two.py"]

    def test_dropping_continues_until_the_budget_is_met(self):
        files = {f"f{i}.py": {"lines": numbered(100), "ranges": [(1, 2)] * 1} for i in range(4)}
        budget = viewer.size_of(numbered(100)) + 10

        windows, dropped = viewer.plan(files, budget=budget)

        assert len(windows) == 1
        assert len(dropped) == 3


class TestEmbed:
    def test_script_end_tag_in_code_cannot_close_the_block(self):
        files = {"a.html": {"lines": ["<script>x</script>", "<!-- note -->"]}}

        text = viewer.embed(files, {"a.html": (1, 2)})

        assert "</script" not in text
        assert "<!--" not in text

    def test_escaped_text_round_trips(self):
        lines = ["<script>x</script>", "<!-- note -->", 'quote " and \\ slash', "é"]
        files = {"a.html": {"lines": lines}}

        data = json.loads(viewer.embed(files, {"a.html": (1, 4)}))

        assert data["a.html"] == {"total": 4, "start": 1, "lines": lines}

    def test_window_records_its_first_line_and_the_file_total(self):
        files = {"a.py": {"lines": numbered(10)}}

        data = json.loads(viewer.embed(files, {"a.py": (4, 6)}))

        assert data["a.py"]["total"] == 10
        assert data["a.py"]["start"] == 4
        assert data["a.py"]["lines"] == numbered(10)[3:6]
