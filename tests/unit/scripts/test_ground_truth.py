import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SKILL / "tests" / "tools"))

import ground_truth  # noqa: E402


def table(card, rows):
    return {"card": card, "blocks": [{"type": "table", "columns": ["a", "b"], "rows": [{"cells": r} for r in rows]}]}


def reports(tmp_path, entry=(), inputs=(), outputs=()):
    d = tmp_path / "reports"
    d.mkdir()
    (d / "entry.json").write_text(json.dumps({"cards": [table("entry.catalog", entry)]}))
    (d / "io.json").write_text(json.dumps({"cards": [table("io.inputs", inputs), table("io.outputs", outputs)]}))
    return d


def truth(tmp_path, entry=(), io=()):
    f = tmp_path / "truth.json"
    f.write_text(json.dumps({"entry_points": [{"kind": "http-route", "key": k, "where": "a.ts:1"} for k in entry],
                             "io": [{"direction": d, "category": "x", "key": k, "where": "a.ts:2"} for d, k in io]}))
    return f


class TestScore:
    def test_matched_missed_and_unmatched(self, tmp_path):
        t = truth(tmp_path, entry=["GET /a", "GET /b"])
        r = reports(tmp_path, entry=[["route", "`GET /a`"], ["route", "`GET /zzz`"]])
        s = ground_truth.score(t, r)["entry"]
        assert s["matched"] == ["GET /a"] and s["missed"] == ["GET /b"]
        assert s["unmatched"] == ["route | GET /zzz"]
        assert s["recall"] == 0.5 and s["precision"] == 0.5

    def test_key_is_found_inside_a_longer_cell_and_backticks_are_ignored(self, tmp_path):
        t = truth(tmp_path, entry=["GET /api/tags"])
        r = reports(tmp_path, entry=[["http route", "`GET /api/tags` (public)"]])
        assert ground_truth.score(t, r)["entry"]["recall"] == 1.0

    def test_one_dossier_row_can_back_two_truth_rows(self, tmp_path):
        t = truth(tmp_path, entry=["GET /a", "POST /a"])
        r = reports(tmp_path, entry=[["route", "GET /a and POST /a"]])
        s = ground_truth.score(t, r)["entry"]
        assert s["recall"] == 1.0 and s["precision"] == 1.0

    def test_inputs_and_outputs_are_scored_apart_and_have_no_precision(self, tmp_path):
        t = truth(tmp_path, io=[("input", "API_KEY"), ("output", "stdout"), ("input", "PORT")])
        r = reports(tmp_path, inputs=[["env", "`API_KEY`"]], outputs=[["stdout/stderr", "stdout"]])
        s = ground_truth.score(t, r)
        assert s["input"]["recall"] == 0.5 and s["input"]["missed"] == ["PORT"]
        assert s["output"]["recall"] == 1.0
        assert "precision" not in s["input"]

    def test_an_empty_side_scores_none_not_a_crash(self, tmp_path):
        t = truth(tmp_path)
        r = reports(tmp_path)
        s = ground_truth.score(t, r)
        assert s["entry"]["recall"] is None and s["entry"]["precision"] is None

    def test_csharp_route_and_double_underscore_key_rows_match(self, tmp_path):
        t = tmp_path / "truth.json"
        t.write_text(json.dumps({
            "entry_points": [{"kind": "http-route", "key": "GET /api/x", "where": "src/Api/XController.cs:12"}],
            "io": [{"direction": "input", "category": "environment variables", "key": "Jwt__Key",
                    "where": "tests/Api.Tests/Helper.cs:7 (test helper)"}]}))
        r = reports(tmp_path, entry=[["http route", "`GET /api/x`", "`src/Api/XController.cs:12`"]],
                    inputs=[["config key", "`Jwt:Key` (env `Jwt__Key`)", "`src/Api/Program.cs:5`"]])

        s = ground_truth.score(t, r)

        assert s["entry"]["recall"] == 1.0 and s["entry"]["precision"] == 1.0
        assert s["input"]["recall"] == 1.0
        assert s["input"]["where"]["Jwt__Key"] == "tests/Api.Tests/Helper.cs:7 (test helper)"

    def test_a_missing_card_counts_as_no_rows(self, tmp_path):
        t = truth(tmp_path, entry=["GET /a"])
        d = tmp_path / "reports"
        d.mkdir()
        assert ground_truth.score(t, d)["entry"]["missed"] == ["GET /a"]


class TestMain:
    def test_prints_figures_and_writes_the_review_file(self, tmp_path, capsys):
        t = truth(tmp_path, entry=["GET /a", "GET /b"], io=[("input", "PORT")])
        r = reports(tmp_path, entry=[["route", "GET /a"]])
        review = tmp_path / "review.md"
        assert ground_truth.main([str(t), str(r), "--review", str(review)]) == 0
        out = capsys.readouterr().out
        assert "entry points: recall 50%" in out and "inputs: recall 0%" in out
        text = review.read_text()
        assert "GET /b" in text and "PORT" in text and "a.ts:1" in text

    def test_usage_error(self, capsys):
        assert ground_truth.main([]) == 2
