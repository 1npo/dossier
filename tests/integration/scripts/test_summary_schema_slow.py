import copy
import json
import os
import subprocess
from pathlib import Path

import pytest

import summary

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the jsonschema package: set DOSSIER_SLOW=1")
SCHEMA = Path(summary.summary_check.SCHEMA_PATH)
CHECK = """
import json, sys
from jsonschema import Draft202012Validator
schema = json.load(open(sys.argv[1]))
Draft202012Validator.check_schema(schema)
v = Draft202012Validator(schema)
docs = json.load(open(sys.argv[2]))
print(json.dumps([sorted(e.json_path for e in v.iter_errors(d)) for d in docs]))
"""


def good():
    return {"schema_version": 1, "dossier_version": "0.8.0", "generated_at": "t", "repo": {"name": "n", "remote": None, "branch": None, "sha": "s", "commit_date": None},
            "languages": [], "extractors": [], "components": [], "entry_points": [], "contributors": [], "contracts": [], "external_dependencies": [],
            "data_stores": [], "risks": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
            "ownership": {"top_owner_share": None, "bus_factor": None, "at_risk_paths": []},
            "change": {"hotspots": [], "cochange_pairs_unlinked": 0}, "gaps": {"unknown": 0, "inference": 0, "assumption": 0, "coverage": 0}}


def documents():
    bad_direction = good()
    bad_direction["contracts"] = [{"name": "a", "direction": "both", "counterparty": "b", "schema_path": None}]
    missing = good()
    del missing["repo"]["sha"]
    extra = good()
    extra["gaps"]["more"] = 1
    return [good(), bad_direction, missing, extra]


class TestAgreesWithJsonschema:
    def test_the_real_validator_and_ours_find_the_same_paths(self, tmp_path):
        docs = documents()
        (tmp_path / "docs.json").write_text(json.dumps(docs))
        (tmp_path / "check.py").write_text(CHECK)

        result = subprocess.run(["uv", "run", "--with", "jsonschema==4.26.0", "python", "-I", str(tmp_path / "check.py"), str(SCHEMA), str(tmp_path / "docs.json")],
                                capture_output=True, text=True, timeout=300)

        assert result.returncode == 0, result.stderr
        theirs = json.loads(result.stdout)
        ours = [sorted(_path(line) for line in summary.validate(copy.deepcopy(d))) for d in docs]
        assert theirs[0] == [] and ours[0] == []
        assert [bool(t) for t in theirs] == [bool(o) for o in ours] == [False, True, True, True]
        assert theirs[1] == ["$.contracts[0].direction"] == ours[1]


def _path(line):
    where = line.split(": ")[2]
    return where
