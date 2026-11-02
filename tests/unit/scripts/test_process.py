import re

import pytest

import buildlog
import process
import render

SHA = "5923c09" + "0" * 33


def rec(step, status="ok", part=None, reason=None, by="prepare", **kw):
    r = {"step": step, "by": by, "status": status, "reason": reason, **kw}
    if part:
        r["part"] = part
    return r


def build_with(*records):
    return {"schema": 1, "sha": SHA, "ref": "main", "records": list(records)}


FULL = [
    rec("pin", details={"trust": {"trusted": True, "why": "tag v1"}}),
    rec("tools", tools=[{"name": "git", "version": "2.47.3"}], details={"languages": [{"name": "Python", "tier": "A"}], "missing": []}),
    rec("copy", part="checkout", details={"submodules": [], "submodules_on": False}),
    rec("copy", part="restore", details={"ecosystems": [{"ecosystem": "python", "status": "ok", "seconds": 12.1, "reason": None}]}),
    rec("measure", counts={"files": 10, "languages": 2, "commits": 5, "contributors": 1}, details={"plan_mode": "full"}),
    rec("extract", status="skipped", reason="No extractors exist for these languages in this version of dossier."),
    rec("read", by="render", counts={"mode": "single", "chunks": 1, "notes_reused": 0, "readers": None}),
    rec("write", by="render", counts={"written": 3, "reused": 0}),
    rec("check", part="render", by="render", counts={"citations": 4, "unresolved": 1, "errors": 0}),
    rec("gaps", by="render", counts={"unknown": 1, "inference": 2, "assumption": 0, "coverage": 3}),
    rec("render", part="render", by="render"),
]


def body_rows(body):
    table = body.split("<tbody>")[1].split("</tbody>")[0]
    return [re.findall(r"<td[^>]*>(.*?)</td>", row, re.S) for row in re.findall(r"<tr>(.*?)</tr>", table, re.S)]


def row_of(body, step):
    return body_rows(body)[buildlog.STEPS.index(step)]


EXTRACT = rec("extract", tools=[{"name": "grimp", "version": "3.17"}, {"name": "scip-python", "version": "0.6.6"}, {"name": "knip", "version": "6.42.0"}],
              details={"adapters": [{"name": "python", "status": "ok", "tools": {"grimp": {"status": "ok"}, "scip-python": {"status": "ok"}, "vulture": {"status": "failed"}}}]})


class TestProcessBody:
    def test_ten_rows_in_order_and_the_tier_line(self):
        body = process.process_body(build_with(*FULL))

        rows = body_rows(body)
        assert len(rows) == len(buildlog.STEPS) == 10
        assert [r[0] for r in rows] == [str(n) for n in range(1, 11)]
        assert rows[0][1].startswith("Pinned the repository") and rows[-1][1].startswith("Rendered the page")
        assert "are measured by tools" in body

    def test_table_has_the_four_columns(self):
        body = process.process_body(build_with(*FULL))

        head = body.split("<thead>")[1].split("</thead>")[0]
        assert re.findall(r"<th[^>]*>(.*?)</th>", head) == ["No.", "Step", "What happened", "Status"]

    def test_step_without_a_record_says_no_record_and_has_a_failed_looking_badge(self):
        body = process.process_body(build_with(*FULL[:2]))

        assert body.count("No record.") == 8
        assert row_of(body, "pin")[3] != row_of(body, "measure")[3]
        assert 'data-variant="destructive">no record' in row_of(body, "measure")[3]

    def test_skipped_step_shows_a_skipped_badge_and_its_reason(self):
        row = row_of(process.process_body(build_with(*FULL)), "extract")

        assert "skipped" in row[3] and "No extractors exist" in row[2]

    def test_ok_step_shows_an_ok_badge(self):
        assert 'data-variant="secondary">ok' in row_of(process.process_body(build_with(*FULL)), "pin")[3]

    def test_text_is_escaped(self):
        body = process.process_body(build_with(rec("pin", details={"trust": {"trusted": False, "why": "<b>x</b>"}})))

        assert "<b>x</b>" not in body

    def test_tools_row_names_the_extractors_with_versions_and_leaves_out_unused_ones(self):
        row = row_of(process.process_body(build_with(*FULL, EXTRACT)), "tools")

        assert "Host: git 2.47.3." in row[2]
        assert "Extractors: grimp 3.17, scip-python 0.6.6." in row[2]
        assert "vulture" not in row[2] and "knip" not in row[2]

    def test_tools_row_says_which_skill_commit_made_the_build(self):
        tools = rec("tools", tools=[], details={"languages": [], "missing": [], "skill": {"path": "/s", "commit": "abcdef1234567", "dirty": True, "unmerged": True}})

        row = row_of(process.process_body(build_with(tools)), "tools")

        assert "Skill: abcdef1, uncommitted changes, UNMERGED." in row[2]

    def test_tools_row_of_an_older_build_has_no_skill_sentence(self):
        assert "Skill:" not in row_of(process.process_body(build_with(*FULL)), "tools")[2]

    def test_check_row_without_a_browser_record_says_not_run_in_red(self):
        status = row_of(process.process_body(build_with(*FULL)), "check")[3]

        assert 'data-variant="destructive">browser: not run' in status

    def test_check_row_with_a_clean_browser_record_says_zero_problems(self):
        b = rec("check", part="browser", by="check_page", counts={"problems": 0}, started="2026-11-01T12:04:05Z")

        status = row_of(process.process_body(build_with(*FULL, b)), "check")[3]

        assert 'data-variant="secondary">browser: 0 problems' in status

    def test_check_row_with_browser_problems_is_red(self):
        b = rec("check", part="browser", by="check_page", counts={"problems": 3}, started="2026-11-01T12:04:05Z")

        status = row_of(process.process_body(build_with(*FULL, b)), "check")[3]

        assert 'data-variant="destructive">browser: 3 problems' in status


class TestRunLine:
    def test_skipped(self):
        assert process.run_line("extract", build_with(*FULL)).startswith("Skipped: No extractors")

    def test_failed(self):
        assert process.run_line("measure", build_with(rec("measure", "failed", reason="boom"))) == "Failed: boom"

    def test_reused(self):
        assert process.run_line("read", build_with(rec("read", "reused", reason="x", by="render"))) == "Reused from the previous build."

    def test_missing_is_none(self):
        assert process.run_line("pin", build_with()) is None

    def test_pin_ok(self):
        assert process.run_line("pin", build_with(*FULL)) == "Commit 5923c09 (main). Trusted ref: tag v1."

    def test_copy_ok_lists_dependencies(self):
        line = process.run_line("copy", build_with(*FULL))

        assert "python installed (12 s)" in line and "Submodules: none." in line

    def test_read_without_readers_says_not_recorded(self):
        assert "number of parallel readers not recorded" in process.run_line("read", build_with(*FULL))

    def test_check_without_browser_record(self):
        assert process.run_line("check", build_with(*FULL)).endswith("Browser check: not run yet.")

    def test_check_with_browser_record(self):
        b = rec("check", part="browser", by="check_page", counts={"problems": 0}, started="2026-11-01T12:04:05Z")

        assert "Browser check at 12:04 UTC: 0 problems." in process.run_line("check", build_with(*FULL, b))

    def test_gaps_counts(self):
        assert process.run_line("gaps", build_with(*FULL)) == "6 open items: 1 unknown, 2 inferred, 0 assumed, 3 coverage."

    def test_write_incremental(self):
        r = rec("write", by="render", counts={"written": 2, "reused": 5})

        assert process.run_line("write", build_with(r)) == "2 reports rewritten, 5 reused."


class TestRenderRecords:
    def measure(self, **details):
        return build_with(rec("measure", details={"reading_mode": "chunked", "chunks": 4, "chunks_with_current_notes": 1, **details}))

    def by_step(self, recs):
        return {r["step"]: r for r in recs}

    def call(self, build, reports, readers=None, v_errors=0):
        return self.by_step(process.render_records(build, reports=reports, readers=readers, v_errors=v_errors,
                                                   cites_checked=7, cites_unresolved=2, gap_counts={"unknown": 1}))

    def test_render_only_reuses_read_and_write(self):
        got = self.call(self.measure(plan_mode="render_only"), {"a": {}})

        assert (got["read"]["status"], got["write"]["status"]) == ("reused", "reused")

    def test_no_reports_skips_read_and_write(self):
        got = self.call(self.measure(plan_mode="full"), {})

        assert got["write"]["status"] == "skipped" and got["write"]["reason"] == "No reports were written in this build."

    def test_full_counts_every_report(self):
        got = self.call(self.measure(plan_mode="full"), {"a": {}, "b": {}}, readers=3)

        assert got["write"]["counts"] == {"written": 2, "reused": 0}
        assert got["read"]["counts"] == {"mode": "chunked", "chunks": 4, "notes_reused": 1, "readers": 3}

    def test_incremental_splits_written_and_reused(self):
        got = self.call(self.measure(plan_mode="incremental", stale=["a"], fresh=["b"]), {"a": {}, "b": {}})

        assert got["write"]["counts"] == {"written": 1, "reused": 1}

    def test_errors_make_the_check_fail(self):
        got = self.call(self.measure(plan_mode="full"), {"a": {}}, v_errors=3)

        assert (got["check"]["status"], got["check"]["reason"]) == ("failed", "3 errors in the reports.")
        assert got["check"]["counts"] == {"citations": 7, "unresolved": 2, "errors": 3}

    def test_every_record_passes_the_record_check(self):
        for r in process.render_records(self.measure(plan_mode="full"), reports={}, readers=None, v_errors=0,
                                        cites_checked=0, cites_unresolved=0, gap_counts={}):
            buildlog.check_record(r)


class TestCoverageItems:
    def statements(self, *records):
        return [i["statement"] for i in process.coverage_items(build_with(*records))]

    def test_no_build_gives_nothing(self):
        assert process.coverage_items(None) == []

    def test_missing_tool(self):
        host = [{"id": "node", "status": "missing", "install": "brew install node"}]

        got = self.statements(rec("tools", details={"host": host, "languages": []}))

        assert got == ["The tool node was not installed, so this build ran without it. Install it with: brew install node"]

    def test_old_tool(self):
        host = [{"id": "node", "status": "old", "version": "20", "needs": "22", "install": "x"}]

        assert "too old (20; it needs 22)" in self.statements(rec("tools", details={"host": host, "languages": []}))[0]

    def test_tier_b_language(self):
        got = self.statements(rec("tools", details={"host": [], "languages": [{"name": "Shell", "tier": "B"}, {"name": "Python", "tier": "A"}]}))

        assert got == ["Shell has basic support only: no import or call graph is extracted for it."]

    def test_skipped_restore_names_each_planned_ecosystem(self):
        r = rec("copy", "skipped", part="restore", reason="Installing dependencies was turned off with --no-restore.", details={"planned": ["python"]})

        assert self.statements(r) == ["Dependencies were not installed for python: Installing dependencies was turned off with --no-restore."]

    def test_no_lockfile_is_not_a_gap(self):
        r = rec("copy", "skipped", part="restore", reason="There is no lockfile at the top of the repository, and dossier installs only from lockfiles.")

        assert self.statements(r) == []

    def test_failed_restore_per_ecosystem(self):
        rows = [{"ecosystem": "python", "status": "failed", "reason": "Installing python dependencies took longer than 1 seconds and was stopped."}]

        got = self.statements(rec("copy", "failed", part="restore", reason="x", details={"ecosystems": rows}))

        assert len(got) == 1 and "took longer than" in got[0]

    def test_submodules_off(self):
        got = self.statements(rec("copy", part="checkout", details={"submodules": ["lib/x"], "submodules_on": False}))

        assert got == ["The submodule lib/x was not analysed. Build with --submodules to include it."]

    def test_submodules_on_is_not_a_gap(self):
        assert self.statements(rec("copy", part="checkout", details={"submodules": ["lib/x"], "submodules_on": True})) == []

    def test_skipped_extract(self):
        assert self.statements(rec("extract", "skipped", reason="why")) == ["The extractors did not run: why"]

    def test_skipped_adapter_when_the_step_itself_ran(self):
        ad = [{"name": "node", "status": "skipped", "reason": "no"}, {"name": "py", "status": "ok", "reason": None}]

        assert self.statements(rec("extract", details={"adapters": ad})) == ["The extractor node did not run: no"]

    def test_other_failed_step_prepare_made(self):
        assert self.statements(rec("measure", "failed", reason="boom")) == ["Step 'measure' failed: boom"]

    def test_records_written_by_render_are_ignored(self):
        assert self.statements(rec("check", "failed", part="render", by="render", reason="3 errors")) == []

    def test_items_are_coverage_kind_on_the_dossier_report(self):
        items = process.coverage_items(build_with(rec("extract", "skipped", reason="why")))

        assert (items[0]["kind"], items[0]["report"]) == ("coverage", "dossier")


class TestCollectGapsExtra:
    def test_empty_extra_changes_nothing(self):
        assert render.collect_gaps({}) == render.collect_gaps({}, ())

    def test_extra_item_is_listed(self):
        item = {"kind": "coverage", "report": "dossier", "statement": "Shell has basic support only.", "how_to_confirm": "Nothing."}

        got = render.collect_gaps({}, [item])

        assert [(g["kind"], g["statement"], g["confirm"]) for g in got] == [("coverage", "Shell has basic support only.", "Nothing.")]


class TestValidateBuild:
    def test_no_build_is_an_error(self):
        assert process.validate_build(None) == (["V10: there is no build.json. Run prepare first."], [])

    def test_missing_step_names_its_number_and_sentence(self):
        recs = [r for r in FULL if r["step"] != "extract"]

        errors, _ = process.validate_build(build_with(*recs))

        assert errors == ["V10: build.json has no record for step 5 'extract' (ran the extractors to find entry points, imports, "
                          "inputs and outputs, data structures and tests)."]

    def test_skipped_without_reason_is_an_error(self):
        recs = [r if r["step"] != "extract" else rec("extract", "skipped") for r in FULL]

        errors, _ = process.validate_build(build_with(*recs))

        assert errors == ["V10: step 'extract' was skipped without a reason."]

    def test_unknown_status_is_an_error(self):
        recs = [r if r["step"] != "pin" else rec("pin", "maybe") for r in FULL]

        errors, _ = process.validate_build(build_with(*recs))

        assert "unknown status 'maybe'" in errors[0]

    def test_complete_build_has_no_errors(self):
        assert process.validate_build(build_with(*FULL))[0] == []

    def test_pending_record_counts(self):
        recs = [r for r in FULL if r["step"] != "render"]

        errors, _ = process.validate_build(build_with(*recs), [rec("render", by="render")])

        assert errors == []


class TestV9:
    def infos(self, extract):
        recs = [r if r["step"] != "extract" else extract for r in FULL]
        return process.validate_build(build_with(*recs))[1]

    def test_skipped_extract_says_nothing_ran(self):
        assert self.infos(rec("extract", "skipped", reason="x")) == ["V9: no extractor ran in this build, so the path filter had nothing to check."]

    def test_counts_line_without_unexpected(self):
        counts = {"paths_seen": 10, "paths_dropped": 3, "dropped_expected": 2, "dropped_outside": 1, "dropped_unexpected": 0}

        got = self.infos(rec("extract", counts=counts, details={"unexpected": []}))

        assert got == ["V9: the path filter removed 3 of 10 extracted paths (2 generated or installed, 1 outside the copy, 0 unexpected)."]

    def test_many_unexpected_paths_list_twenty_and_count_the_rest(self):
        paths = [f"p{i:02d}.py" for i in range(25)]

        got = self.infos(rec("extract", counts={"dropped_unexpected": 25}, details={"unexpected": paths}))

        assert got[1].endswith("p19.py, and 5 more (see build.json)") and "p20.py" not in got[1]


class TestPartialCards:
    SELF = [{"id": "grimp"}, {"id": "scip-python"}, {"id": "semgrep"}, {"id": "tree-sitter-language-pack"}, {"id": "vulture"}, {"id": "import-linter"}]

    def tools(self, missing=()):
        return rec("tools", details={"self_installing": self.SELF, "missing": list(missing), "languages": []})

    def extract(self, status="ok", reason=None, **tools):
        return rec("extract", status=status, reason=reason, details={"adapters": [{"name": "python", "status": "ok", "tools": tools}]})

    def test_no_build_means_no_badges(self):
        assert process.partial_cards(None) == {}

    def test_missing_tool_marks_the_cards_that_need_it(self):
        got = process.partial_cards(build_with(self.tools(["scip-python"]), self.extract()))

        assert {c for c in got} == {"components.catalog", "interactions.flows", "interactions.graph"}
        assert got["components.catalog"] == "Made without scip-python: it is not installed."

    def test_failed_tool_gives_its_own_reason(self):
        status = {"grimp": {"status": "failed", "reason": "No module named foo."}}

        got = process.partial_cards(build_with(self.tools(), self.extract(**status)))

        assert got["reading.order"] == "Made without grimp: No module named foo."

    def test_cards_with_two_absent_tools_list_both(self):
        status = {"grimp": {"status": "failed", "reason": "boom"}, "scip-python": {"status": "skipped", "reason": "Node is missing"}}

        got = process.partial_cards(build_with(self.tools(), self.extract(**status)))

        assert got["interactions.graph"] == "Made without grimp: boom. Made without scip-python: Node is missing."

    def test_skipped_extract_marks_every_card_with_a_tool(self):
        got = process.partial_cards(build_with(self.tools(), self.extract("skipped", "No extractors exist.")))

        assert got["entry.catalog"] == "Made without semgrep: No extractors exist."
        assert "change.dead-code" in got and "reading.order" in got

    def test_a_missing_tool_for_another_language_marks_nothing(self):
        got = process.partial_cards(build_with(self.tools(["dependency-cruiser", "scip-typescript"]), self.extract()))

        assert got == {}

    def test_ok_tools_mark_nothing(self):
        status = {"grimp": {"status": "ok", "reason": None}}

        assert process.partial_cards(build_with(self.tools(), self.extract(**status))) == {}


class TestCheckLine:
    def line(self, **counts):
        build = build_with(rec("check", part="render", by="render", counts={"citations": 4, "unresolved": 1, "errors": 0, **counts}))
        return process.run_line("check", build)

    def test_tool_finding_and_component_counts_are_said_when_present(self):
        got = self.line(v5_candidates=12, v5_open=3, v4=2)

        assert "Tool findings: 12 found, 3 without a decision. Components: 2 problems." in got

    def test_name_count_is_said_when_present(self):
        assert "Names: 3 not found in the code they cite." in self.line(v2=3)

    def test_the_page_audit_is_said_when_it_ran(self):
        audit = rec("check", part="audit", by="render", counts={"v11": 2})
        build = build_with(rec("check", part="render", by="render", counts={"citations": 4, "unresolved": 0, "errors": 0}), audit)

        assert " Page: 2 problems." in process.run_line("check", build)

    def test_no_page_sentence_without_an_audit_record(self):
        assert "Page:" not in self.line()

    def test_old_records_without_the_counts_read_as_before(self):
        assert "Tool findings" not in self.line()

    def test_render_records_store_the_counts_on_the_check_record(self):
        build = build_with(rec("measure", details={"plan_mode": "full"}))

        got = process.render_records(build, reports={}, readers=None, v_errors=0, cites_checked=1, cites_unresolved=0, gap_counts={},
                                     check_counts={"v5_candidates": 5, "v5_open": 0, "v4": 0, "unbacked": {}})

        assert got[0]["counts"]["v5_candidates"] == 5 and "unbacked" not in got[0]["counts"]
