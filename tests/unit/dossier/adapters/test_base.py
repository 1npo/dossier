from dossier.adapters import base
from contexts import make_context


class TestFailureReason:
    def test_a_multi_line_message_gives_its_first_line(self):
        assert base.failure_reason(RuntimeError("semgrep failed (exit 2):\nstack")) == "semgrep failed (exit 2):"

    def test_an_empty_message_gives_the_type_name(self):
        assert base.failure_reason(ValueError()) == "ValueError"

    def test_an_empty_first_line_gives_an_empty_reason(self):
        assert base.failure_reason(RuntimeError("\nsecond line")) == ""


class TestRead:
    def test_a_utf8_file_gives_its_text(self, tmp_path):
        (tmp_path / "a.txt").write_text("héllo\n", encoding="utf-8")

        got = make_context(checkout=tmp_path).read("a.txt")

        assert got == "héllo\n"

    def test_a_missing_file_gives_none(self, tmp_path):
        assert make_context(checkout=tmp_path).read("missing.txt") is None

    def test_a_file_that_is_not_utf8_gives_none(self, tmp_path):
        (tmp_path / "b.bin").write_bytes(b"\xff\xfe\x00")

        assert make_context(checkout=tmp_path).read("b.bin") is None


class TestToolOk:
    def test_it_records_ok_with_no_reason(self, tmp_path):
        ctx = make_context(checkout=tmp_path)

        ctx.tool_ok("semgrep")

        assert ctx.tool_status == {"semgrep": {"status": "ok", "reason": None}}
        assert list(ctx.tool_status["semgrep"]) == ["status", "reason"]


class TestToolSkipped:
    def test_it_records_skipped_with_the_reason(self, tmp_path):
        ctx = make_context(checkout=tmp_path)

        ctx.tool_skipped("vulture", "There are no Python files to check.")

        assert ctx.tool_status == {"vulture": {"status": "skipped", "reason": "There are no Python files to check."}}
        assert list(ctx.tool_status["vulture"]) == ["status", "reason"]


class TestToolFailed:
    def test_it_records_failed_with_the_reason(self, tmp_path):
        ctx = make_context(checkout=tmp_path)

        ctx.tool_failed("grimp", "boom")

        assert ctx.tool_status == {"grimp": {"status": "failed", "reason": "boom"}}
        assert list(ctx.tool_status["grimp"]) == ["status", "reason"]

    def test_a_later_call_replaces_the_earlier_status(self, tmp_path):
        ctx = make_context(checkout=tmp_path)
        ctx.tool_ok("grimp")

        ctx.tool_failed("grimp", "boom")

        assert ctx.tool_status["grimp"] == {"status": "failed", "reason": "boom"}
