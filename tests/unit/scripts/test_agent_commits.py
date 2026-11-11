import pytest

import gather


def label_of(message):
    """The agent label the history collectors give a commit message, or None when it is not an agent's."""
    marker = gather.AGENT_MSG.search(message)
    if not marker:
        return None
    return next((label for label, pat in gather.AGENT_LABELS if gather.re.search(pat, marker.group(0), gather.re.I)), "other")


class TestAgentMessage:
    @pytest.mark.parametrize("message", [
        "Fix the parser\n\nAgent-Logs-Url: https://github.com/o/r/sessions/abc123\nCo-authored-by: Ann <ann@x.io>",
        "Subject\n\nagent-logs-url: https://example.com/logs/1",
    ])
    def test_an_agent_logs_url_line_marks_a_copilot_commit(self, message):
        assert label_of(message) == "Copilot"

    @pytest.mark.parametrize("message,label", [
        ("Add x\n\nCo-authored-by: Copilot <175728472+Copilot@users.noreply.github.com>", "Copilot"),
        ("Add x\n\nCo-authored-by: copilot-swe-agent[bot] <198982749+Copilot@users.noreply.github.com>", "Copilot"),
        ("Add x\n\nCo-authored-by: Claude <noreply@anthropic.com>", "Claude"),
        ("Add x\n\nCo-authored-by: claude <claude@users.noreply.github.com>", "Claude"),
    ])
    def test_a_co_authored_by_trailer_from_a_known_agent_marks_the_commit(self, message, label):
        assert label_of(message) == label

    @pytest.mark.parametrize("message", [
        "Add x\n\nCo-authored-by: Ann Lee <ann@example.com>",
        "Add x\n\nSee the Agent-Logs-Url field in the docs",
        "Mention Agent-Logs-Url: in the middle of a sentence, not a trailer",
        "Plain commit",
    ])
    def test_other_commits_are_not_marked(self, message):
        assert label_of(message) is None
