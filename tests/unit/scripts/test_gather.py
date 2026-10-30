import json
from datetime import datetime, timezone

import pytest

import gather


def days():
    return {"2026-01-05": {"a": {"x.py": [1, 10, 2]}, "z": {"x.py": [1, 1, 1], "y.py": [2, 4, 0]}},
            "2026-01-07": {"a": {"x.py": [3, 5, 5]}}}


class TestPackActivity:
    def test_keeps_days_and_totals_nothing_when_it_fits(self):
        out = gather.pack_activity(days(), {"a"}, {"x.py"})
        assert out["grain"] == "day" and out["trimmed"] == 0
        assert out["files"] == ["x.py", "y.py"] and out["gone"] == [1]
        assert out["rows"]["2026-01-05"]["a"] == [[0, 1, 10, 2]]

    def test_people_outside_the_top_are_grouped_under_an_empty_id(self):
        out = gather.pack_activity(days(), {"a"}, {"x.py", "y.py"})
        assert sorted(out["rows"]["2026-01-05"]) == ["", "a"]

    def test_falls_back_to_weeks_when_days_are_too_big(self):
        out = gather.pack_activity(days(), {"a"}, {"x.py", "y.py"}, cap=140)
        assert out["grain"] == "week" and list(out["rows"]) == ["2026-01-05"]
        assert out["rows"]["2026-01-05"]["a"] == [[0, 4, 15, 7]]

    def test_drops_the_least_changed_files_last(self):
        out = gather.pack_activity(days(), {"a"}, {"x.py", "y.py"}, cap=120)
        assert out["grain"] == "month" and out["files"] == ["x.py"] and out["trimmed"] == 1

    def test_bucket_keys(self):
        assert gather.bucket_key("2026-01-07", "week") == "2026-01-05"
        assert gather.bucket_key("2026-01-07", "month") == "2026-01-01"


class TestParseCommit:
    HEAD = b"abc123\x1fAnn Lee\x1fann@x.io\x1f2026-01-02T03:04:05+00:00\0\n"

    def test_reads_who_when_and_each_file_with_its_line_counts(self):
        raw = self.HEAD + b"5\t2\tsrc/a.py\0-\t-\tlogo.png\0"

        got = gather.parse_commit(raw)

        assert got[:4] == ("abc123", "Ann Lee", "ann@x.io", "2026-01-02T03:04:05+00:00")
        assert got[4] == [(5, 2, None, "src/a.py"), (0, 0, None, "logo.png")]

    def test_rename_carries_the_old_and_the_new_path(self):
        raw = self.HEAD + b"0\t0\t\0old/a.py\0new/a.py\0" + b"1\t0\tb.py\0"

        got = gather.parse_commit(raw)

        assert got[4] == [(0, 0, "old/a.py", "new/a.py"), (1, 0, None, "b.py")]

    def test_commit_with_no_files_has_no_entries(self):
        assert gather.parse_commit(self.HEAD)[4] == []

    def test_record_without_a_header_is_skipped(self):
        assert gather.parse_commit(b"garbage") is None


class TestCreditHistory:
    AS_OF = datetime(2026, 6, 30, tzinfo=timezone.utc)

    def commit(self, who, day, *entries):
        return ("sha", who, f"{who}@x.io", f"{day}T12:00:00+00:00", list(entries))

    def cid_of(self, name, email):
        return None if name == "bot" else name

    def credit(self, commits, wanted):
        return gather.credit_history(commits, wanted, self.cid_of, self.AS_OF)

    def test_commits_before_a_rename_are_credited_to_the_current_path(self):
        commits = [self.commit("ann", "2026-03-01", (0, 0, "old.py", "new.py")),
                   self.commit("bob", "2025-01-01", (7, 0, None, "old.py"))]

        per_file, _, _ = self.credit(commits, {"new.py"})

        assert per_file["new.py"] == {"ann": [1, 1, 0], "bob": [1, 0, 7]}

    def test_a_path_reused_after_a_rename_is_not_mistaken_for_the_renamed_file(self):
        commits = [self.commit("ann", "2026-04-01", (3, 0, None, "a.py")),
                   self.commit("ann", "2026-03-01", (0, 0, "a.py", "b.py")),
                   self.commit("bob", "2025-01-01", (7, 0, None, "a.py"))]

        per_file, _, _ = self.credit(commits, {"a.py", "b.py"})

        assert per_file["a.py"] == {"ann": [1, 1, 3]}
        assert per_file["b.py"] == {"ann": [1, 1, 0], "bob": [1, 0, 7]}

    def test_recent_means_the_year_before_the_given_date(self):
        commits = [self.commit("ann", "2025-07-01", (1, 0, None, "a.py")), self.commit("ann", "2025-06-01", (1, 0, None, "a.py"))]

        per_file, _, _ = self.credit(commits, {"a.py"})

        assert per_file["a.py"]["ann"][:2] == [2, 1]

    def test_bots_are_skipped_entirely(self):
        commits = [self.commit("bot", "2026-03-01", (1, 0, None, "a.py"))]

        per_file, people, _ = self.credit(commits, {"a.py"})

        assert per_file == {} and people == {}

    def test_bulk_commit_counts_for_the_person_but_credits_no_file(self):
        commits = [self.commit("ann", "2026-03-01", *[(1, 0, None, f"f{i}.py") for i in range(gather.BULK_FILES + 1)])]

        per_file, people, _ = self.credit(commits, {"f1.py"})

        assert per_file == {} and people["ann"][0] == 1

    def test_files_outside_the_wanted_set_are_ignored(self):
        commits = [self.commit("ann", "2026-03-01", (1, 0, None, "vendor/x.py"))]

        per_file, _, _ = self.credit(commits, {"a.py"})

        assert per_file == {}

    def test_last_change_is_the_newest_commit_on_the_file(self):
        commits = [self.commit("ann", "2026-03-01", (1, 0, None, "a.py")), self.commit("bob", "2025-01-01", (1, 0, None, "a.py"))]

        _, _, last = self.credit(commits, {"a.py"})

        assert last["a.py"].strftime("%Y-%m") == "2026-03"


class TestBlend:
    def test_weights_lines_commits_and_recent_commits(self):
        got = gather.blend([1, 1], [3, 1], [1, 3])

        assert got == pytest.approx([0.5 * 0.5 + 0.3 * 0.75 + 0.2 * 0.25, 0.5 * 0.5 + 0.3 * 0.25 + 0.2 * 0.75])

    def test_a_component_that_totals_zero_is_dropped_and_the_rest_renormalised(self):
        got = gather.blend([1, 1], [3, 1], [0, 0])

        assert got == pytest.approx([(0.5 * 0.5 + 0.3 * 0.75) / 0.8, (0.5 * 0.5 + 0.3 * 0.25) / 0.8])

    def test_everything_zero_gives_zero_shares(self):
        assert gather.blend([0, 0], [0, 0], [0, 0]) == [0, 0]


class TestShortNames:
    def test_first_names_are_used_when_they_are_unique(self):
        assert gather.short_names(["Ann Lee", "Bob Ray"]) == ["Ann", "Bob"]

    def test_a_shared_first_name_gets_a_last_initial(self):
        assert gather.short_names(["Ann Lee", "Ann Ray", "Bob"]) == ["Ann L.", "Ann R.", "Bob"]

    def test_a_single_word_name_is_kept_whole(self):
        assert gather.short_names(["1npo"]) == ["1npo"]


class TestFitRows:
    ROWS = [["big.py", 1000, "2026-01", [[0, 900, 5, 1]]], ["tiny.py", 1, "2026-01", [[0, 1, 0, 0]]]]

    def test_rows_that_fit_are_all_kept(self):
        assert gather.fit_rows(self.ROWS, 10_000) == (self.ROWS, 0)

    def test_the_smallest_least_changed_files_are_dropped_first(self):
        cap = len(json.dumps(self.ROWS[:1], separators=(",", ":")))

        rows, dropped = gather.fit_rows(self.ROWS, cap)

        assert rows == self.ROWS[:1] and dropped == 1
