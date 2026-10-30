import gather


class TestKnowledgeMap:
    def knowledge(self, git_repo):
        facts, _ = gather.profile(str(git_repo))
        return facts["knowledge"]

    def row(self, k, path):
        return next(r for r in k["files"] if r[0] == path)

    def test_bots_are_left_out_and_everyone_else_is_listed(self, git_repo):
        k = self.knowledge(git_repo)

        assert sorted(c["name"] for c in k["contributors"]) == ["Ann Lee", "Dana Cole"]
        assert k["others"] is None

    def test_a_person_with_no_commit_for_six_months_before_head_is_departed(self, git_repo):
        k = self.knowledge(git_repo)

        departed = {c["name"]: c["departed"] for c in k["contributors"]}

        assert departed == {"Ann Lee": False, "Dana Cole": True}

    def test_departure_is_measured_from_the_head_date_not_from_today(self, git_repo):
        k = self.knowledge(git_repo)

        assert k["date"] == "2026-06-01" and k["departed_months"] == 6

    def test_a_renamed_file_keeps_its_history_at_the_current_path(self, git_repo):
        k = self.knowledge(git_repo)

        paths = [r[0] for r in k["files"]]
        ann = next(i for i, c in enumerate(k["contributors"]) if c["name"] == "Ann Lee")

        assert "src/main_py" in paths and "src/app_py" not in paths
        assert [t for t in self.row(k, "src/main_py")[3] if t[0] == ann][0][2] == 3

    def test_surviving_lines_come_from_blame(self, git_repo):
        k = self.knowledge(git_repo)
        dana = next(i for i, c in enumerate(k["contributors"]) if c["name"] == "Dana Cole")

        cells = self.row(k, "old/legacy_py")[3]

        assert cells == [[dana, 3, 1, 0]]

    def test_recent_commits_exclude_those_more_than_a_year_before_head(self, git_repo):
        k = self.knowledge(git_repo)
        ann = next(i for i, c in enumerate(k["contributors"]) if c["name"] == "Ann Lee")

        cell = next(t for t in self.row(k, "src/main_py")[3] if t[0] == ann)

        assert cell[2:] == [3, 2]

    def test_the_last_change_is_the_month_of_the_newest_commit(self, git_repo):
        k = self.knowledge(git_repo)

        assert self.row(k, "src/main_py")[2] == "2026-06" and self.row(k, "old/legacy_py")[2] == "2025-01"

    def test_blame_ran_on_every_file_so_nothing_is_estimated(self, git_repo):
        k = self.knowledge(git_repo)

        assert k["approx_files"] == 0
