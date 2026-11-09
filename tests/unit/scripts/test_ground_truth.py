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
        assert s["input"]["where"]["Jwt__Key"] == ["tests/Api.Tests/Helper.cs:7 (test helper)"]

    def test_a_missing_card_counts_as_no_rows(self, tmp_path):
        t = truth(tmp_path, entry=["GET /a"])
        d = tmp_path / "reports"
        d.mkdir()
        assert ground_truth.score(t, d)["entry"]["missed"] == ["GET /a"]


class TestSharedKeysAndCitations:
    def test_truth_rows_sharing_a_key_keep_their_own_where(self, tmp_path):
        t = tmp_path / "truth.json"
        t.write_text(json.dumps({"entry_points": [
            {"kind": "ci", "key": "workflow_dispatch", "where": "a.yml:10"},
            {"kind": "ci", "key": "workflow_dispatch", "where": "b.yml:10"}], "io": []}))
        s = ground_truth.score(t, reports(tmp_path))["entry"]
        assert s["where"]["workflow_dispatch"] == ["a.yml:10", "b.yml:10"]
        assert s["missed"] == ["workflow_dispatch", "workflow_dispatch"]
        assert s["missed_where"] == ["a.yml:10", "b.yml:10"]

    def test_review_lists_each_shared_key_row_with_its_own_line(self, tmp_path):
        t = tmp_path / "truth.json"
        t.write_text(json.dumps({"entry_points": [
            {"kind": "ci", "key": "exit 1", "where": "a.sh:30"},
            {"kind": "ci", "key": "exit 1", "where": "a.sh:45"}], "io": []}))
        text = ground_truth.review(ground_truth.score(t, reports(tmp_path)))
        assert "(truth: a.sh:30)" in text and "(truth: a.sh:45)" in text

    def test_a_key_inside_a_citation_does_not_match(self, tmp_path):
        t = truth(tmp_path, io=[("output", "201")])
        r = reports(tmp_path, outputs=[["response", "409 on a clash", "[[ConduitContext.cs:171-201]]"]])
        s = ground_truth.score(t, r)["output"]
        assert s["missed"] == ["201"]

    def test_a_key_in_the_text_still_matches_beside_a_citation(self, tmp_path):
        t = truth(tmp_path, io=[("output", "201")])
        r = reports(tmp_path, outputs=[["response", "201 on create", "[[A.cs:1-2]]"]])
        assert ground_truth.score(t, r)["output"]["recall"] == 1.0

    def test_a_citation_label_is_visible_text_and_matches(self, tmp_path):
        t = truth(tmp_path, entry=["src/App/Program.cs"])
        r = reports(tmp_path, entry=[["program", "[[src/App/Program.cs:12-97|src/App/Program.cs]]"]])
        assert ground_truth.score(t, r)["entry"]["recall"] == 1.0

    def test_a_citation_target_does_not_match_when_it_has_a_different_label(self, tmp_path):
        t = truth(tmp_path, entry=["src/App/Program.cs"])
        r = reports(tmp_path, entry=[["program", "[[src/App/Program.cs:12-97|Program.cs]]"]])
        assert ground_truth.score(t, r)["entry"]["missed"] == ["src/App/Program.cs"]

    def test_unmatched_rows_keep_their_citations(self, tmp_path):
        t = truth(tmp_path, entry=["GET /a"])
        r = reports(tmp_path, entry=[["route", "GET /z", "[[A.cs:1-2]]"]])
        assert ground_truth.score(t, r)["entry"]["unmatched"] == ["route | GET /z | [[A.cs:1-2]]"]


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
