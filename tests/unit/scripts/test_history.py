from datetime import datetime, timezone

import history

AS_OF = datetime(2026, 6, 30, tzinfo=timezone.utc)


def record(sha, who, day, parents, message, numstat=b""):
    head = f"\x1e{sha}\x1f{who}\x1f{who}@x.io\x1f{day}T12:00:00+00:00\x1f{parents}\x1f{message}".encode()
    return head + b"\0" + numstat


def commit(sha, who, day, *entries, parents="p"):
    return history.Commit(sha, who, f"{who}@x.io", f"{day}T12:00:00+00:00", tuple(parents.split()), "msg", tuple(entries))


def cid_of(name, email):
    return None if name == "skip" else name


def run_fold(commits, wanted, bulk_files=400):
    return history.fold(commits, wanted, cid_of, AS_OF, bulk_files)


class TestParseLog:
    def test_plain_commit_reads_header_parents_and_files(self):
        data = record("a1", "ann", "2026-01-02", "p1", "Add x\n", b"5\t2\tsrc/a.py\0")

        got = list(history.parse_log(data))

        assert got == [history.Commit("a1", "ann", "ann@x.io", "2026-01-02T12:00:00+00:00", ("p1",), "Add x", ((5, 2, None, "src/a.py"),))]

    def test_rename_carries_both_paths(self):
        data = record("a1", "ann", "2026-01-02", "p1", "mv", b"0\t0\t\0old.py\0new.py\0")

        got = list(history.parse_log(data))

        assert got[0].entries == ((0, 0, "old.py", "new.py"),)

    def test_merge_has_two_parents_and_no_entries(self):
        data = record("m1", "ann", "2026-01-02", "p1 p2", "Merge branch 'x'\n")

        got = list(history.parse_log(data))

        assert got[0].parents == ("p1", "p2") and got[0].entries == ()

    def test_cut_off_header_is_dropped(self):
        data = record("a1", "ann", "2026-01-02", "p1", "ok", b"1\t1\ta.py\0") + b"\x1ebad\x1fann"

        got = list(history.parse_log(data))

        assert [c.sha for c in got] == ["a1"]

    def test_drop_last_removes_the_final_record(self):
        data = record("a1", "ann", "2026-01-02", "p1", "one") + record("a2", "ann", "2026-01-03", "p1", "two")

        got = list(history.parse_log(data, drop_last=True))

        assert [c.sha for c in got] == ["a1"]

    def test_message_with_tabs_and_newlines_stays_whole(self):
        data = record("a1", "ann", "2026-01-02", "p1", "Subject\n\n\tbody\tline\nmore\n", b"1\t0\ta.py\0")

        got = list(history.parse_log(data))

        assert got[0].message == "Subject\n\n\tbody\tline\nmore" and got[0].subject == "Subject"
        assert got[0].entries == ((1, 0, None, "a.py"),)


class TestFold:
    def test_commits_before_a_rename_are_credited_to_the_new_path(self):
        commits = [commit("c2", "ann", "2026-03-01", (0, 0, "old.py", "new.py")),
                   commit("c1", "bob", "2025-01-01", (7, 0, None, "old.py"))]

        out = run_fold(commits, {"new.py"})

        assert out.files["new.py"]["commits"] == 2
        assert out.files["new.py"]["authors"] == {"ann": 1, "bob": 1}

    def test_windows_count_back_from_the_pinned_date(self):
        commits = [commit("c2", "ann", "2026-06-01", (3, 1, None, "a.py")), commit("c1", "ann", "2025-01-01", (10, 0, None, "a.py"))]

        f = run_fold(commits, {"a.py"}).files["a.py"]

        assert (f["commits"], f["commits_12m"], f["lines_changed"], f["lines_changed_12m"]) == (2, 1, 14, 4)
        assert f["last_changed"].date().isoformat() == "2026-06-01"

    def test_bulk_commit_is_listed_and_credits_no_file_or_pair(self):
        entries = [(1, 0, None, f"f{i}.py") for i in range(4)]
        commits = [commit("b1", "ann", "2026-02-01", *entries)]

        out = run_fold(commits, {e[3] for e in entries}, bulk_files=3)

        assert out.files == {} and not out.pairs
        assert out.bulk[0]["sha"] == "b1" and out.bulk[0]["files"] == 4

    def test_pairs_count_commits_that_touch_both_files(self):
        commits = [commit(f"c{i}", "ann", "2026-02-0%d" % (i + 1), (1, 0, None, "a.py"), (1, 0, None, "b.py"), (1, 0, None, "c.py")) for i in range(2)]

        out = run_fold(commits, {"a.py", "b.py", "c.py"})

        assert out.pairs[("a.py", "b.py")] == 2 and len(out.pairs) == 3

    def test_paths_not_wanted_are_ignored(self):
        out = run_fold([commit("c1", "ann", "2026-02-01", (1, 0, None, "a.py"), (1, 0, None, "x.lock"))], {"a.py"})

        assert list(out.files) == ["a.py"] and not out.pairs

    def test_merge_commits_credit_no_file_and_no_person(self):
        out = run_fold([commit("m1", "ann", "2026-02-01", parents="p1 p2")], {"a.py"})

        assert out.people == {} and [c.sha for c in out.commits] == ["m1"] and out.author_of == {"m1": "ann"}

    def test_excluded_identity_is_not_counted(self):
        out = run_fold([commit("c1", "skip", "2026-02-01", (1, 0, None, "a.py"))], {"a.py"})

        assert out.files == {} and out.people == {}

    def test_people_get_first_last_and_recent_counts(self):
        commits = [commit("c2", "ann", "2026-06-01"), commit("c1", "ann", "2024-01-01")]

        who = run_fold(commits, set()).people["ann"]

        assert (who["commits"], who["commits_12m"]) == (2, 1)
        assert who["first"].year == 2024 and who["last"].month == 6
