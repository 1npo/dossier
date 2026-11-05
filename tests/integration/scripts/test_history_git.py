import functools
from pathlib import Path

import pytest

import gather
import history
import sandbox


@pytest.fixture
def world(tmp_path, history_repo):
    top = str(history_repo)
    facts, _ = gather.collect(top, "HEAD", 400_000, None)
    sha = facts["repo"]["sha"]
    area = tmp_path / "area"
    run = functools.partial(sandbox.run, area=area, cwd=Path(top))

    def collect(handed=None, timeout=60):
        return history.collect(top, sha, run, handed or facts["history_input"], timeout)

    collect.facts, collect.top, collect.sha, collect.run = facts, top, sha, run
    return collect


def items(data, kind):
    return [i for i in history.items_of(data) if i["kind"] == kind]


class TestCollect:
    def test_meta_is_ok_on_a_full_clone(self, world):
        meta = history.meta_of(world())

        assert meta["status"] == "ok" and meta["reasons"] == [] and meta["shallow"] is False
        assert meta["commits_seen"] == meta["commits_total"]
        assert meta["as_of"] == "2026-06-01"

    def test_files_follow_a_rename_and_count_each_commit(self, world):
        files = {f["path"]: f for f in items(world(), "file")}

        assert files["src/d2.py"]["commits"] == 2 and "src/d.py" not in files
        assert files["src/a.py"]["commits"] == 4 and files["src/a.py"]["authors"] == {"ann@x.io": 3, "bob@x.io": 1}

    def test_files_changed_together_make_pairs(self, world):
        pairs = {(p["a"], p["b"]): p for p in items(world(), "pair")}

        assert pairs[("src/a.py", "src/b.py")]["co_commits"] == 3
        assert pairs[("src/a.py", "src/c.py")]["share"] == round(100 * 3 / 3)

    def test_people_carry_type_and_assisted_count(self, world):
        people = {p["name"]: p for p in items(world(), "person")}

        assert people["Claude"]["type"] == "agent" and people["dependabot[bot]"]["type"] == "bot"
        assert people["Bob Ray"]["assisted"] == 1 and people["Ann Lee"]["assisted"] == 0

    def test_assistant_item_counts_marked_human_commits_and_their_files(self, world):
        assistant = items(world(), "assistant")

        assert assistant == [{"kind": "assistant", "path": "", "name": "Claude", "commits": 1, "files": {"src/a.py": 1}}]

    def test_bulk_commit_is_listed_and_credits_no_file(self, world, monkeypatch):
        monkeypatch.setattr(gather, "BULK_FILES", 2)

        data = world()

        assert [b["subject"] for b in items(data, "bulk")] == ["feat: step 3", "feat: step 2", "feat: step 1"]
        assert items(data, "bulk")[0]["files"] == 3 and items(data, "bulk")[0]["author"] == "Ann Lee"
        assert "src/c.py" not in {f["path"] for f in items(data, "file")}

    def test_blame_covers_every_file_on_a_full_clone(self, world):
        meta = history.meta_of(world())

        assert meta["blame_done"] == meta["blame_total"] > 0

    def test_write_puts_the_envelope_where_candidates_load_finds_it(self, world, tmp_path):
        import candidates
        data = world()

        history.write(tmp_path / "out", data)

        assert len(candidates.load(tmp_path / "out")["history"]) == len(history.items_of(data))
