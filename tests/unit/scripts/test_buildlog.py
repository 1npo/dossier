import os
import subprocess

import pytest

import buildlog

SHA = "5923c09" + "0" * 33


@pytest.fixture
def path(tmp_path):
    return buildlog.start(tmp_path, repo="r", sha=SHA, ref="main", version="0.6.0", options={})


def rec(step="pin", status="ok", **kw):
    return {"step": step, "by": "prepare", "status": status, **kw}


class TestStart:
    def test_second_start_keeps_the_first_as_prev(self, tmp_path):
        buildlog.start(tmp_path, repo="r", sha=SHA, ref="a", version="1", options={})

        buildlog.start(tmp_path, repo="r", sha=SHA, ref="b", version="1", options={})

        assert buildlog.load(tmp_path / buildlog.PREV)["ref"] == "a"
        assert buildlog.load(tmp_path)["ref"] == "b"

    def test_build_id_ends_with_short_sha(self, path):
        assert buildlog.load(path)["build_id"].endswith("-5923c09")


class TestAppend:
    def test_keeps_earlier_records_in_order(self, path):
        buildlog.append(path, rec("pin"))
        buildlog.append(path, rec("tools"))

        assert [r["step"] for r in buildlog.load(path)["records"]] == ["pin", "tools"]

    def test_fills_times(self, path):
        r = buildlog.append(path, rec())

        assert r["started"] and r["ended"] and r["seconds"] == 0.0

    def test_crash_during_replace_leaves_old_file_intact(self, path, monkeypatch):
        buildlog.append(path, rec("pin"))
        before = path.read_text()
        monkeypatch.setattr(os, "replace", lambda *a: (_ for _ in ()).throw(OSError("boom")))

        with pytest.raises(OSError):
            buildlog.append(path, rec("tools"))

        assert path.read_text() == before


class TestCheckRecord:
    def test_unknown_step_rejected(self):
        with pytest.raises(ValueError, match="step"):
            buildlog.check_record(rec("bogus"))

    def test_unknown_status_rejected(self):
        with pytest.raises(ValueError, match="status"):
            buildlog.check_record(rec(status="maybe"))

    def test_skipped_without_reason_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            buildlog.check_record(rec(status="skipped"))

    def test_unknown_writer_rejected(self):
        with pytest.raises(ValueError, match="writer"):
            buildlog.check_record({"step": "pin", "by": "claude", "status": "ok"})


class TestStep:
    def test_exception_records_failed_with_reason_and_reraises(self, path):
        with pytest.raises(RuntimeError):
            with buildlog.step(path, "measure"):
                raise RuntimeError("it broke\nsecond line")

        last = buildlog.load(path)["records"][-1]
        assert (last["status"], last["reason"]) == ("failed", "it broke")

    def test_normal_exit_records_ok_with_filled_fields(self, path):
        with buildlog.step(path, "measure", part="x") as r:
            r["counts"] = {"files": 3}

        last = buildlog.load(path)["records"][-1]
        assert (last["status"], last["part"], last["counts"]) == ("ok", "x", {"files": 3})


class TestLatest:
    def test_returns_last_record_for_the_same_step_and_part(self, path):
        buildlog.append(path, rec("copy", part="restore", counts={"n": 1}))
        buildlog.append(path, rec("copy", part="restore", counts={"n": 2}))

        assert buildlog.latest(buildlog.load(path), "copy", "restore")["counts"] == {"n": 2}

    def test_missing_step_is_none(self, path):
        assert buildlog.latest(buildlog.load(path), "pin") is None


class TestLoad:
    def test_absent_is_none(self, tmp_path):
        assert buildlog.load(tmp_path) is None


class TestRecordBrowser:
    def test_clean_run_is_ok(self, path):
        buildlog.record_browser(path, 0, 12)

        last = buildlog.load(path)["records"][-1]
        assert (last["step"], last["part"], last["by"], last["status"]) == ("check", "browser", "check_page", "ok")
        assert last["counts"] == {"problems": 0, "diagrams_checked": 12}

    def test_problems_fail_with_a_reason(self, path):
        buildlog.record_browser(path, 2, 12)

        last = buildlog.load(path)["records"][-1]
        assert (last["status"], last["reason"]) == ("failed", "2 problems in the browser check.")


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=False, capture_output=True)


@pytest.fixture
def skill_repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "a.css").write_text("x\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "one")
    return tmp_path


class TestSkillState:
    def test_clean_repo_is_neither_dirty_nor_unmerged(self, skill_repo):
        state = buildlog.skill_state(skill_repo)

        assert state["dirty"] is False
        assert state["unmerged"] is False
        assert len(state["commit"]) == 40

    def test_edited_file_is_dirty(self, skill_repo):
        (skill_repo / "a.css").write_text("y\n")

        assert buildlog.skill_state(skill_repo)["dirty"] is True

    def test_conflicted_merge_is_unmerged(self, skill_repo):
        git(skill_repo, "switch", "-q", "-c", "other")
        (skill_repo / "a.css").write_text("other\n")
        git(skill_repo, "commit", "-q", "-am", "other")
        git(skill_repo, "switch", "-q", "main")
        (skill_repo / "a.css").write_text("main\n")
        git(skill_repo, "commit", "-q", "-am", "main")
        git(skill_repo, "merge", "other")

        state = buildlog.skill_state(skill_repo)

        assert state["unmerged"] is True
        assert state["dirty"] is True

    def test_folder_outside_git_has_no_values(self, tmp_path):
        state = buildlog.skill_state(tmp_path)

        assert state == {"path": str(tmp_path), "commit": None, "dirty": None, "unmerged": None}
