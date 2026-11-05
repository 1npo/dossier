import history
import workflow


def commit(sha, subject, parents=("p",), body=""):
    msg = subject + ("\n\n" + body if body else "")
    return history.Commit(sha, "ann", "ann@x.io", "2026-01-01T00:00:00+00:00", tuple(parents), msg, ())


def row(rows, name):
    return next(r for r in rows if r["convention"] == name)


class TestBranchName:
    def test_reads_the_three_merge_forms(self):
        assert workflow.branch_name("Merge branch 'feat/x'") == "feat/x"
        assert workflow.branch_name("Merge pull request #12 from o/fix/y") == "fix/y"
        assert workflow.branch_name("merged feat/z into main") == "feat/z"

    def test_ordinary_subject_has_none(self):
        assert workflow.branch_name("feat: add a thing") is None


class TestRows:
    def make(self, commits, sizes=None, tags=(), default="main"):
        return workflow.rows(commits, sizes or {}, list(tags), default)

    def test_always_six_rows_in_the_spec_order(self):
        got = self.make([commit("a", "x")])

        assert [r["convention"] for r in got] == list(workflow.ROWS)

    def test_no_merges_names_no_branches_and_calls_history_linear(self):
        got = self.make([commit("a", "one"), commit("b", "two")])

        assert row(got, "branch naming and strategy")["observed"] == "Default branch main. No branch names are recorded in merge commits."
        assert row(got, "merge style")["observed"] == "linear history"
        assert row(got, "typical PR size")["observed"] == "No merge commits to measure."

    def test_merge_pull_request_gives_prefixes_and_merge_style(self):
        commits = [commit("m1", "Merge pull request #3 from o/feat/a", ("p", "q")), commit("m2", "Merge pull request #2 from o/feat/b", ("p", "q")),
                   commit("m3", "Merge pull request #1 from o/fix/c", ("p", "q")), commit("c", "work")]

        got = self.make(commits, {"m1": (2, 10), "m2": (4, 30), "m3": (6, 20)})

        assert row(got, "branch naming and strategy")["observed"] == "Default branch main. Most common prefixes: feat (2), fix (1)."
        assert row(got, "branch naming and strategy")["evidence"] == "3 merge commits name a branch."
        assert row(got, "merge style")["observed"] == "merge commits"
        assert row(got, "typical PR size")["observed"] == "About 4 files and 20 changed lines per merge (median)."

    def test_merged_slash_form_is_understood(self):
        got = self.make([commit("m", "merged feat/x", ("p", "q"))] + [commit(f"c{i}", "w") for i in range(20)])

        assert "feat (1)" in row(got, "branch naming and strategy")["observed"]

    def test_pull_request_numbers_in_subjects_mean_squash_merges(self):
        got = self.make([commit("a", "Add x (#1)"), commit("b", "Add y (#2)"), commit("c", "plain")])

        assert row(got, "merge style")["observed"] == "squash merges"

    def test_conventional_subjects_are_counted(self):
        got = self.make([commit("a", "feat: a"), commit("b", "fix(core): b"), commit("c", "Did a thing")])

        r = row(got, "commit message style")
        assert r["observed"] == "Conventional commits"
        assert r["evidence"].startswith("2 of 3 subjects follow the pattern; the median subject is ")

    def test_free_form_when_few_follow_the_pattern(self):
        got = self.make([commit("a", "Did one"), commit("b", "Did two"), commit("c", "feat: x")])

        assert row(got, "commit message style")["observed"] == "Free-form sentences"

    def test_review_rate_counts_trailers_on_merge_commits(self):
        commits = [commit("m1", "Merge branch 'a'", ("p", "q"), "Reviewed-by: Bob <b@x.io>"), commit("m2", "Merge branch 'b'", ("p", "q"))]

        got = self.make(commits)

        assert row(got, "review rate")["observed"] == "1 of 2 merge commits carry a Reviewed-by or Approved-by line."
        assert row(got, "review rate")["commits"] == ["m1"]

    def test_release_cadence_for_none_one_and_three_tags(self):
        none = row(self.make([commit("a", "x")]), "release cadence")
        one = row(self.make([commit("a", "x")], tags=[("v1", "2026-01-01")]), "release cadence")
        three = row(self.make([commit("a", "x")], tags=[("v1", "2026-01-01"), ("v2", "2026-01-11"), ("v3", "2026-02-10")]), "release cadence")

        assert (none["observed"], none["evidence"]) == ("No tags at this commit.", "-")
        assert (one["observed"], one["evidence"]) == ("One tag.", "Newest tag v1 on 2026-01-01.")
        assert (three["observed"], three["evidence"]) == ("3 tags; a median of 20 days apart.", "Newest tag v3 on 2026-02-10.")

    def test_example_commits_are_at_most_three(self):
        commits = [commit(f"m{i}", f"Merge branch 'x{i}'", ("p", "q")) for i in range(6)]

        got = self.make(commits)

        assert len(row(got, "merge style")["commits"]) == 3
