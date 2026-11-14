from dossier.checks import reports as checks_reports
from dossier.checks import v14


def components(surface, name="store"):
    return {"components": {"cards": [{"card": "components.detail", "entries": [{"component": name, "fields": {"public_surface": surface}}]}]}}


def test_a_name_with_a_labelled_citation_passes():
    assert v14.v14(components("[[src/s.py:10-60|Store]], [[src/s.py:30-40|Store.save_alert]]")) == []


def test_a_backticked_name_without_a_citation_is_an_error():
    errors = v14.v14(components("`Store`, [[src/s.py:30-40|Store.save_alert]], `helper`"))

    assert len(errors) == 1 and errors[0].startswith("V14:") and "`Store`" in errors[0] and "`helper`" in errors[0] and "store" in errors[0]
    assert "save_alert`" not in errors[0]


def test_a_backticked_label_inside_a_citation_is_cited():
    assert v14.v14(components("[[src/s.py:1-9|`Store`]]")) == []


def test_plain_prose_and_other_cards_and_fields_are_left_alone():
    assert v14.v14(components("Nothing is exported.")) == []
    other = {"components": {"cards": [{"card": "components.catalog", "entries": [{"component": "x", "fields": {"public_surface": "`A`"}}]}]}}
    assert v14.v14(other) == []
    assert v14.v14({}) == []


def test_validate_reports_it_as_an_error():
    result = checks_reports.validate(components("`Store`"), {}, None, None)

    assert any(e.startswith("V14:") for e in result["errors"])
