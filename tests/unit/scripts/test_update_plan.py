import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import dossier  # noqa: E402


class TestUpdatePlan:
    def make(self, tmp_path):
        (tmp_path / "reports").mkdir()
        (tmp_path / "reports" / "entry.json").write_text(json.dumps({"report": "entry", "cards": []}))
        facts = {"repo": {"sha": "b" * 40}, "delta": {"changed": [], "files_changed": 0}}
        state = {"last_sha": "a" * 40}
        return facts, state

    def test_state_saved_by_the_previous_minor_version_plans_a_full_rebuild(self, tmp_path):
        facts, state = self.make(tmp_path)

        plan = dossier.update_plan(tmp_path, tmp_path, state, facts, "0.10.0", False)

        assert plan["mode"] == "full"
        assert plan["why"] == f"the skill changed from 0.10.0 to {dossier.VERSION}"
        assert dossier.VERSION.split(".")[:2] != ["0", "10"]
