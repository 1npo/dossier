import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dossier.py"


def fake(bin_dir, name, out):
    f = bin_dir / name
    f.write_text("#!/bin/sh\nprintf '%s\\n' " + shlex.quote(out) + "\n")
    f.chmod(0o755)


@pytest.fixture
def world(tmp_path, hygiene_repo):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "git").symlink_to(shutil.which("git"))
    fake(bin_dir, "uv", "uv 0.11.19")
    env = {"PATH": str(bin_dir), "DOSSIER_HOME": str(tmp_path / "home"),
           "DOSSIER_CONFIG": str(tmp_path / "cfg.json"), "DOSSIER_CACHE": str(tmp_path / "cache")}

    def prepare(*args):
        r = subprocess.run([sys.executable, str(SCRIPT), "prepare", hygiene_repo.path, *args], capture_output=True, text=True, env=env)
        return r.returncode, (json.loads(r.stdout) if r.stdout.strip().startswith("{") else None), r.stderr

    out = tmp_path / "home" / "hygiene"
    return type("W", (), {"prepare": staticmethod(prepare), "out": out,
                          "repo": hygiene_repo})


def build_of(world):
    return json.loads((world.out / "build.json").read_text())


def steps(build):
    return [(r["step"], r.get("part"), r["status"]) for r in build["records"]]


class TestPrepareStops:
    def test_missing_node_stops_with_code_2(self, world):
        code, payload, _ = world.prepare()

        assert code == 2 and payload["stopped"] == "missing_tools"
        assert {m["id"] for m in payload["missing"]} >= {"node", "npm"}
        assert steps(build_of(world)) == [("pin", None, "ok"), ("tools", None, "failed")]

    def test_allow_missing_then_stops_to_ask_about_restore(self, world):
        code, payload, _ = world.prepare("--ref", "main", "--allow-missing")

        assert code == 3 and payload["stopped"] == "restore_question"
        assert payload["will_run"][0]["command"] == "uv sync --frozen"
        last = build_of(world)["records"][-1]
        assert (last["part"], last["status"], last["reason"]) == ("restore", "skipped", "Waiting for your answer about installing dependencies.")


class TestPrepareRuns:
    def test_restore_no_completes_and_is_remembered(self, world):
        code, payload, err = world.prepare("--ref", "main", "--allow-missing", "--restore", "no")

        assert code == 0, err
        state = json.loads((world.out / "state.json").read_text())
        assert state["restore"]["answer"] == "no"
        assert [s[0] for s in steps(build_of(world))] == ["pin", "tools", "copy", "copy", "extract", "measure"]
        assert payload["checkout"]["verified"] and payload["extract"]["status"] == "ok"
        extract = next(r for r in build_of(world)["records"] if r["step"] == "extract")
        assert [a["name"] for a in extract["details"]["adapters"]] == ["python", "repo"]

    def test_prepare_writes_the_history_and_keeps_the_hand_over_out_of_facts(self, world):
        code, _, err = world.prepare("--ref", "main", "--allow-missing", "--restore", "no")

        facts = json.loads((world.out / "facts.json").read_text())
        measure = next(r for r in build_of(world)["records"] if r["step"] == "measure")
        assert code == 0, err
        assert (world.out / "extract" / "history.json").exists()
        assert "history_input" not in facts and facts["history"]["status"] == "ok"
        assert measure["details"]["history"]["kind"] == "meta" and measure["details"]["plan_mode"]

    def test_stored_no_is_used_next_time(self, world):
        world.prepare("--ref", "main", "--allow-missing", "--restore", "no")

        code, _, _ = world.prepare("--ref", "main", "--allow-missing")

        restore = [r for r in build_of(world)["records"] if r.get("part") == "restore"][-1]
        assert code == 0 and "--restore yes" in restore["reason"]

    def test_feature_branch_does_not_restore_without_allow_ref(self, world):
        code, payload, _ = world.prepare("--ref", "feature/x", "--allow-missing", "--restore", "yes")

        restore = [r for r in build_of(world)["records"] if r.get("part") == "restore"][-1]
        assert code == 0 and restore["status"] == "skipped" and "--allow-ref" in restore["reason"]
        assert payload["trust"]["trusted"] is False

    def test_no_restore_flag_skips(self, world):
        code, _, _ = world.prepare("--ref", "main", "--allow-missing", "--no-restore")

        restore = [r for r in build_of(world)["records"] if r.get("part") == "restore"][-1]
        assert code == 0 and "--no-restore" in restore["reason"]

    def test_bad_ref_exits_with_a_message(self, world):
        code, _, err = world.prepare("--ref", "nope", "--allow-missing")

        assert code == 1 and "not a commit" in err
