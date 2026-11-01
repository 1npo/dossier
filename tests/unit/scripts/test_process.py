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


class TestProcessBody:
    def test_ten_steps_in_order_and_the_tier_line(self):
        body = process.process_body(build_with(*FULL))

        sentences = re.findall(r"<li><p>(.*?)</p>", body)
        assert len(sentences) == 10
        assert sentences[0].startswith("Pinned the repository") and sentences[-1].startswith("Rendered the page")
        assert "are measured by tools" in body

    def test_step_without_a_record_says_no_record(self):
        body = process.process_body(build_with(*FULL[:2]))

        assert body.count("No record.") == 8

    def test_text_is_escaped(self):
        body = process.process_body(build_with(rec("pin", details={"trust": {"trusted": False, "why": "<b>x</b>"}})))

        assert "<b>x</b>" not in body


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
