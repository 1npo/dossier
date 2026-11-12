import json
import sys
from pathlib import Path

from dossier.cli import common  # noqa: E402
from dossier.cli.commands import prepare  # noqa: E402


class TestUpdatePlan:
    def make(self, tmp_path):
        (tmp_path / "reports").mkdir()
        (tmp_path / "reports" / "entry.json").write_text(json.dumps({"report": "entry", "cards": []}))
        facts = {"repo": {"sha": "b" * 40}, "delta": {"changed": [], "files_changed": 0}}
        state = {"last_sha": "a" * 40}
        return facts, state

    def test_state_saved_by_the_previous_minor_version_plans_a_full_rebuild(self, tmp_path):
        facts, state = self.make(tmp_path)

        plan = prepare.update_plan(tmp_path, tmp_path, state, facts, "0.10.0", False)

        assert plan["mode"] == "full"
        assert plan["why"] == f"the skill changed from 0.10.0 to {common.VERSION}"
        assert common.VERSION.split(".")[:2] != ["0", "10"]
