import incremental


def report(*cites, text=""):
    return {"headline": "h", "summary": "s", "blocks": [{"type": "text", "text": text, "conf": "confirmed", "cite": list(cites)}]}


def hunks_of(table):
    return lambda path: table.get(path, [])


def plan(reports, changed, hunks=None, corrections=None, commits=1, expected=None, allow_shift=True):
    return incremental.plan(reports, expected or list(reports), changed, hunks_of(hunks or {}), False, corrections or {}, commits, allow_shift)


class TestParseHunks:
    def test_reads_counts_and_defaults_missing_ones_to_one(self):
        diff = "@@ -10,2 +10,5 @@ def f\n+x\n@@ -30 +33 @@\n"

        assert incremental.parse_hunks(diff) == [(10, 2, 10, 5), (30, 1, 33, 1)]

    def test_pure_insertion_has_zero_old_lines(self):
        assert incremental.parse_hunks("@@ -4,0 +5,3 @@\n") == [(4, 0, 5, 3)]


class TestShiftRange:
    def test_lines_after_an_insertion_move_down(self):
        assert incremental.shift_range(20, 30, [(4, 0, 5, 3)]) == (23, 33)

    def test_lines_before_a_change_stay(self):
        assert incremental.shift_range(1, 5, [(10, 2, 10, 6)]) == (1, 5)

    def test_replaced_lines_inside_the_range_are_a_conflict(self):
        assert incremental.shift_range(8, 12, [(10, 2, 10, 6)]) is None

    def test_insertion_inside_the_range_is_a_conflict(self):
        assert incremental.shift_range(8, 12, [(10, 0, 11, 2)]) is None

    def test_insertion_just_after_the_range_is_not(self):
        assert incremental.shift_range(8, 12, [(12, 0, 13, 2)]) == (8, 12)

    def test_deletion_above_moves_lines_up(self):
        assert incremental.shift_range(20, 25, [(2, 3, 2, 0)]) == (17, 22)


class TestPlan:
    def test_untouched_report_is_fresh(self):
        res = plan({"data": report("src/db.py:1-5")}, {"src/other.py": "M"})

        assert res["stale"] == {}

    def test_edit_inside_cited_lines_makes_the_report_stale(self):
        res = plan({"data": report("src/db.py:10-20")}, {"src/db.py": "M"}, {"src/db.py": [(12, 1, 12, 3)]})

        assert "data" in res["stale"]

    def test_edit_outside_cited_lines_shifts_the_citation(self):
        res = plan({"data": report("src/db.py:10-20")}, {"src/db.py": "M"}, {"src/db.py": [(1, 0, 2, 4)]})

        assert res["stale"] == {}
        assert res["shifts"] == {"data": {"src/db.py:10-20": "src/db.py:14-24"}}

    def test_whole_file_citation_is_stale_when_the_file_changes(self):
        res = plan({"data": report("src/db.py")}, {"src/db.py": "M"})

        assert "data" in res["stale"]

    def test_shifting_off_treats_any_change_as_stale(self):
        res = plan({"data": report("src/db.py:10-20")}, {"src/db.py": "M"}, {"src/db.py": [(1, 0, 2, 4)]}, allow_shift=False)

        assert "data" in res["stale"]

    def test_deleted_file_makes_the_report_stale(self):
        res = plan({"data": report("src/db.py:1-5")}, {"src/db.py": "D"})

        assert "data" in res["stale"]

    def test_change_under_a_cited_directory_is_stale(self):
        res = plan({"code-tour": report("src/api")}, {"src/api/new.py": "A"})

        assert "code-tour" in res["stale"]

    def test_file_added_next_to_a_cited_file_is_stale(self):
        res = plan({"interfaces": report("src/routes/a.py:1-9")}, {"src/routes/b.py": "A"})

        assert "interfaces" in res["stale"]

    def test_pending_correction_makes_the_report_stale(self):
        res = plan({"data": report("src/db.py:1-5")}, {}, corrections={"data": ["C001"]})

        assert "pending correction C001" in res["stale"]["data"][0]

    def test_overview_is_stale_when_commits_were_added(self):
        res = plan({"overview": report("README.md:1-3"), "data": report("src/db.py:1-5")}, {"src/x.py": "M"}, commits=2)

        assert list(res["stale"]) == ["overview"]

    def test_overview_stays_fresh_at_the_same_commit(self):
        res = plan({"overview": report("README.md:1-3")}, {}, commits=0)

        assert res["stale"] == {}

    def test_missing_report_is_stale(self):
        res = plan({}, {}, expected=["data"])

        assert "data" in res["stale"]

    def test_gaps_follows_any_stale_report(self):
        res = plan({"data": report("src/db.py"), "gaps": report("facts:git")}, {"src/db.py": "M"})

        assert set(res["stale"]) == {"data", "gaps"}

    def test_gaps_stays_fresh_when_nothing_else_is_stale(self):
        res = plan({"data": report("src/db.py:1-2"), "gaps": report("facts:git")}, {"src/x.py": "M"})

        assert res["stale"] == {}

    def test_manifest_fact_citation_is_stale_when_dependencies_changed(self):
        res = incremental.plan({"delivery": report("facts:manifests")}, ["delivery"], {}, hunks_of({}), True, {}, 1)

        assert "delivery" in res["stale"]


class TestApplyShifts:
    def test_rewrites_cite_lists_and_inline_citations_but_not_diagrams(self):
        rep = {"blocks": [{"type": "text", "text": "See [[a.py:10-20, b.py:3|label]].", "cite": ["a.py:10-20"]},
                          {"type": "diagram", "mermaid": "flowchart LR\n a[[a.py:10-20]]", "cite": ["a.py:10-20"]}]}

        out = incremental.apply_shifts(rep, {"a.py:10-20": "a.py:14-24"})

        assert out["blocks"][0]["text"] == "See [[a.py:14-24, b.py:3|label]]."
        assert out["blocks"][0]["cite"] == ["a.py:14-24"]
        assert out["blocks"][1]["mermaid"] == "flowchart LR\n a[[a.py:10-20]]"
        assert out["blocks"][1]["cite"] == ["a.py:14-24"]
