import checks

FLAGS = "Stale feature flags and unused routes are not detected for Python."


def gaps(extract):
    return [(g["report"], g["statement"]) for g in checks.validate({}, extract)["gaps"] if g["statement"] == FLAGS]


class TestStaleFlagsGap:
    def test_python_extraction_adds_the_fixed_item_for_the_change_report(self):
        assert gaps({"graph": [{"kind": "module", "path": "a.py", "module": "a"}]}) == [("change", FLAGS)]

    def test_no_python_graph_adds_nothing(self):
        assert gaps({"dead": []}) == []
