import history
import markers


def commit(sha, message, parents=("p",), entries=()):
    return history.Commit(sha, "ann", "a@x.io", "2026-01-01T00:00:00+00:00", tuple(parents), message, tuple(entries))


class TestScan:
    def test_finds_each_rule_on_comment_lines(self):
        text = "x = 1  # HACK: temporary\n# XXX fix\n// work around the bug\n-- see JIRA-123\n/* ISSUE#45 */\n"

        items, _ = markers.scan("a.py", text)

        assert [(i["line"], i["rule"]) for i in items] == [(1, "marker.hack"), (2, "marker.xxx"), (3, "marker.workaround"),
                                                           (4, "marker.bug-id"), (5, "marker.bug-id")]
        assert items[0]["snippet"] == "x = 1  # HACK: temporary" and items[0]["end_line"] == 1 and items[0]["kind"] == "marker"

    def test_text_outside_comments_is_ignored(self):
        items, todos = markers.scan("a.py", 'name = "HACK"\nprint("work around")\n')

        assert items == [] and todos == 0

    def test_lowercase_hack_does_not_match(self):
        items, _ = markers.scan("a.py", "# a hack here\n")

        assert items == []

    def test_work_around_in_two_words_matches_in_any_case(self):
        items, _ = markers.scan("a.py", "# Work around a bug\n# workAround\n")

        assert [i["rule"] for i in items] == ["marker.workaround"] * 2

    def test_bug_id_forms(self):
        items, _ = markers.scan("a.py", "# BUG-12\n# PROJ-77 done\n# UTF-8 is fine\n")

        assert [i["line"] for i in items] == [1, 2, 3]

    def test_todo_and_fixme_are_counted_not_listed(self):
        items, todos = markers.scan("a.py", "# TODO: a\n# FIXME: b TODO c\nx = 1\n")

        assert items == [] and todos == 3

    def test_one_line_can_hold_two_rules(self):
        items, _ = markers.scan("a.py", "# HACK: work around PROJ-9\n")

        assert sorted(i["rule"] for i in items) == ["marker.bug-id", "marker.hack", "marker.workaround"]


class TestDecisionDocs:
    def test_matches_adr_decision_and_design_documents(self):
        tree = ["docs/adr/0001.md", "decisions/x.md", "docs/system-design.md", "docs/architecture/a.md", "src/a.py", "README.md"]

        assert markers.decision_docs(tree) == ["decisions/x.md", "docs/adr/0001.md", "docs/architecture/a.md", "docs/system-design.md"]


class TestLongCommits:
    BODY = "Subject\n\n" + "\n".join(f"line {i}" for i in range(8))

    def test_eight_body_lines_make_a_long_commit(self):
        got = markers.long_commits([commit("a", self.BODY, entries=[(1, 0, None, "a.py")])])

        assert got == [{"kind": "long-commit", "path": "", "sha": "a", "subject": "Subject", "lines": 8, "files": 1}]

    def test_trailers_and_blank_lines_are_not_counted(self):
        message = "Subject\n\n" + "\n".join(f"line {i}" for i in range(7)) + "\n\nCo-authored-by: X <x@y>\nSigned-off-by: Y <y@z>"

        assert markers.long_commits([commit("a", message)]) == []

    def test_merge_commits_are_skipped(self):
        assert markers.long_commits([commit("a", self.BODY, parents=("p", "q"))]) == []
