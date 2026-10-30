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
