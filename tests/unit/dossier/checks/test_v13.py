from dossier.checks import v13

TREE = frozenset({"app/api/a.py", "app/db/b.py", "app/jobs/c.py", "app/jobs/d.py"})
LINES = {"app/api/a.py": 400, "app/db/b.py": 400, "app/jobs/c.py": 100, "app/jobs/d.py": 50}
FACTS = {"file_lines": LINES}


def catalog():
    rows = [{"cells": ["api", "app/api/"]}, {"cells": ["db", "app/db/"]}, {"cells": ["jobs", "app/jobs/"]}]
    return {"cards": [{"card": "components.catalog", "blocks": [{"type": "table", "rows": rows}]}]}


def table(*rows, **extra):
    return {"card": "data.truth", "blocks": [{"type": "table", "rows": [{"cells": c, "cite": cite} for c, cite in rows]}], **extra}


def reports(entry):
    return {"components": catalog(), "data": {"cards": [entry]}}


def run(entry, extract=None):
    return v13.v13(reports(entry), extract or {}, TREE, FACTS)


def test_a_card_that_misses_a_component_is_an_error_for_a_big_one_and_a_warning_for_a_small_one():
    errors, warnings, _, counts = run(table((["orders", "x", "y"], ["app/api/a.py:1-5"])))

    assert [e for e in errors if "the component db" in e] and counts["v13"] == 1
    assert [w for w in warnings if "the component jobs" in w]
    assert not [e for e in errors if "component api" in e]


def test_covering_every_component_by_citation_or_by_name_passes():
    entry = table((["orders", "x", "y"], ["app/api/a.py:1-5"]), (["rows", "stored by db", "y"], []), (["j", "x", "y"], ["app/jobs/c.py"]))

    errors, warnings, _, _ = run(entry)

    assert errors == [] and warnings == []


def test_a_not_applicable_entry_with_a_reason_passes_and_becomes_an_assumption():
    entry = table((["orders", "x", "y"], ["app/api/a.py:1-5"]), not_applicable=[
        {"component": "db", "reason": "it holds no data of its own"}, {"component": "jobs", "reason": "it only calls api"}])

    errors, warnings, gaps, _ = run(entry)

    assert errors == [] and warnings == []
    assert [g["kind"] for g in gaps] == ["assumption", "assumption"] and "it holds no data of its own" in gaps[0]["statement"]


def test_a_not_applicable_entry_without_a_reason_is_an_error():
    entry = table((["o", "x", "y"], ["app/api/a.py"]), not_applicable=[{"component": "db", "reason": " "}])

    errors, _, _, _ = run(entry)

    assert any("without a reason" in e for e in errors)


def test_every_component_with_an_entry_point_needs_a_flow():
    flows = {"card": "interactions.flows", "blocks": [{"type": "diagram", "source": "flowchart TB\n a-->b", "cite": ["app/api/a.py:1"]}]}
    extract = {"entry_points": [{"path": "app/jobs/c.py"}]}

    errors, _, _, _ = run(flows, extract)

    assert any("no flow for the component jobs" in e for e in errors)


def test_no_catalog_means_nothing_to_check():
    assert v13.v13({"data": {"cards": [table((["a", "b", "c"], []))]}}, {}, TREE, FACTS)[:3] == ([], [], [])
