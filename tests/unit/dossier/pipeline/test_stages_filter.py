import pytest

from dossier.pipeline import extract, stages


def fake_extract(counts, unexpected=()):
    def run(**kw):
        return {"status": "ok", "reason": None, "counts": counts, "details": {"adapters": [], "unexpected": list(unexpected)}}
    return run


@pytest.fixture
def quiet(monkeypatch, tmp_path):
    monkeypatch.setattr(stages, "record", lambda *a, **k: None)
    monkeypatch.setattr(stages.toolcheck, "load_tools", lambda: {"tools": []})
    monkeypatch.setattr(stages.registry, "detect", lambda langs: [])
    monkeypatch.setattr(stages.candidates, "tool_status", lambda out: {})
    return tmp_path


def run(tmp_path, opts):
    return stages.stage_extract(tmp_path, "top", "sha", tmp_path, tmp_path, [], {"trusted": True}, opts, {}, frozenset(), tmp_path)


def test_a_filter_that_dropped_many_unexpected_paths_stops_prepare_with_exit_4(monkeypatch, quiet):
    monkeypatch.setattr(extract, "run_extract", fake_extract({"paths_seen": 100, "paths_dropped": 57, "dropped_unexpected": 57}, ["a\\b.py"]))

    with pytest.raises(stages.Stop) as stop:
        run(quiet, stages.Options())

    assert stop.value.code == 4
    assert stop.value.payload["stopped"] == "extract_filter" and stop.value.payload["first_dropped_paths"] == ["a\\b.py"]


def test_allow_dropped_lets_prepare_go_on(monkeypatch, quiet):
    monkeypatch.setattr(extract, "run_extract", fake_extract({"paths_seen": 100, "paths_dropped": 57, "dropped_unexpected": 57}))

    assert run(quiet, stages.Options(allow_dropped=True))["status"] == "ok"


def test_a_few_dropped_paths_do_not_stop_prepare(monkeypatch, quiet):
    monkeypatch.setattr(extract, "run_extract", fake_extract({"paths_seen": 100, "paths_dropped": 2, "dropped_unexpected": 2}))

    assert run(quiet, stages.Options())["status"] == "ok"
