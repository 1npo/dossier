import re

import measured


class Refs:
    def mark(self, cites):
        return f"[{','.join(cites)}]"


def row(name, observed="o", evidence="e", commits=()):
    return {"kind": "workflow", "path": "", "convention": name, "observed": observed, "evidence": evidence, "commits": list(commits)}


class TestWorkflow:
    def test_no_history_leaves_the_placeholder(self):
        assert measured.body("contributors.workflow", {"extract": {}}, Refs()) is None

    def test_one_row_per_workflow_item_in_order_with_commit_citations(self):
        items = [{"kind": "meta"}, row("branch naming and strategy", commits=["abc"]), row("merge style", "linear history", "0 merge commits")]

        html = measured.body("contributors.workflow", {"extract": {"history": items}}, Refs())

        assert 'id="t-contributors-workflow"' in html
        assert re.findall(r"<td>(branch naming and strategy|merge style)</td>", html) == ["branch naming and strategy", "merge style"]
        assert "[commit:abc]" in html and "linear history" in html
