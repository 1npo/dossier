import json
import subprocess
import sys
from pathlib import Path

import pytest

import candidates

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dossier.py"


@pytest.fixture
def world(tmp_path, hygiene_repo):
    out = tmp_path / "home" / "hygiene"
    (out / "extract").mkdir(parents=True)
    items = candidates.assign_ids("io_candidates", [
        {"path": "app.py", "line": 1, "end_line": 1, "category": "env-var", "rule": "dossier.python.input.env-var", "snippet": 'os.getenv("A")'},
        {"path": "app.py", "line": 2, "end_line": 2, "category": "stdout", "rule": "dossier.python.output.stdout", "snippet": "print(1)"}])
    (out / "extract" / "io_candidates.json").write_text(json.dumps({"schema": 1, "sha": "s", "adapters": {"python": {"items": items}}}))
    env = {"PATH": "/usr/bin:/bin", "DOSSIER_HOME": str(tmp_path / "home"), "DOSSIER_CONFIG": str(tmp_path / "cfg.json"),
           "DOSSIER_CACHE": str(tmp_path / "cache")}

    def run(*args):
        r = subprocess.run([sys.executable, str(SCRIPT), "candidates", hygiene_repo.path, *args], capture_output=True, text=True, env=env)
        return r.returncode, r.stdout, r.stderr

    run.out, run.items = out, items
    return run


class TestCandidatesCommand:
    def test_lists_the_findings_of_a_report(self, world):
        code, out, err = world("--report", "io")

        assert code == 0, err
        assert "== io.inputs (Inputs): 1 findings in 1 groups ==" in out and "== io.outputs (Outputs): 1 findings in 1 groups ==" in out

    def test_open_prints_only_what_no_report_decided(self, world):
        (world.out / "reports").mkdir()
        (world.out / "reports" / "io.json").write_text(json.dumps({"cards": [{"card": "io.inputs", "dismissed": [
            {"cand": [world.items[0]["id"]], "reason": "Not used."}]}]}))

        code, out, _ = world("--report", "io", "--open")

        assert code == 0 and "io.inputs" not in out and "io.outputs" in out

    def test_open_prints_nothing_when_everything_is_decided(self, world):
        (world.out / "reports").mkdir()
        ids = [i["id"] for i in world.items]
        (world.out / "reports" / "io.json").write_text(json.dumps({"cards": [{"card": "io.inputs", "dismissed": [{"cand": ids, "reason": "x"}]}]}))

        assert world("--report", "io", "--open")[:2] == (0, "")

    def test_json_gives_the_same_data(self, world):
        code, out, _ = world("--report", "io", "--json")

        assert code == 0 and [c["card"] for c in json.loads(out)["cards"]] == ["io.inputs", "io.outputs"]

    def test_unknown_report_is_refused_with_the_list(self, world):
        code, _, err = world("--report", "nope")

        assert code != 0 and "io" in err

    def test_missing_extractor_output_says_to_run_prepare(self, tmp_path, hygiene_repo):
        env = {"PATH": "/usr/bin:/bin", "DOSSIER_HOME": str(tmp_path / "empty"), "DOSSIER_CONFIG": str(tmp_path / "c.json"),
               "DOSSIER_CACHE": str(tmp_path / "k")}

        r = subprocess.run([sys.executable, str(SCRIPT), "candidates", hygiene_repo.path, "--report", "io"], capture_output=True, text=True, env=env)

        assert r.returncode != 0 and "Run prepare first" in r.stderr
