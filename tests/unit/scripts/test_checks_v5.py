import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent / "scripts"))
import checks  # noqa: E402


def item(i, group, path="src/a.py", line=3, category="env-var", rule="dossier.python.input.env-var"):
    return {"id": i, "group": group, "path": path, "line": line, "category": category, "rule": rule, "snippet": "x"}


EXTRACT = {"io_candidates": [item("io-1", "iog-1"), item("io-2", "iog-1", line=9), item("io-3", "iog-2", category="stdout", rule="r.out")],
           "entry_points": [{"id": "ep-1", "group": "epg-1", "path": "m.py", "line": 1, "kind": "main-guard", "rule": "r.main"}]}


def row(*cells, **kw):
    return {"cells": list(cells), "conf": "confirmed", "cite": ["a.py"], **kw}


def card(cid, rows=(), **kw):
    return {"card": cid, "blocks": [{"type": "table", "columns": ["A", "B"], "rows": list(rows)}], **kw}


def reports(*cards):
    out = {}
    for c in cards:
        out.setdefault(c["card"].split(".")[0], {"cards": []})["cards"].append(c)
    return out


class TestV5:
    def test_undecided_candidates_error_with_the_fixed_text(self):
        errors, _, _, counts = checks.v5({}, EXTRACT)

        assert any(e.startswith("V5: 2 tool findings for") and "have no decision, for example io-1 (src/a.py:3, dossier.python.input.env-var)" in e
                   and e.endswith("Keep, merge or dismiss them.") for e in errors)
        assert counts == {"v5_candidates": 4, "v5_open": 4}

    def test_group_id_covers_every_member(self):
        reps = reports(card("io.inputs", [row("env", "x", cand=["iog-1"])]), card("io.outputs", dismissed=[{"cand": ["io-3"], "reason": "Tests."}]),
                       card("entry.catalog", [row("main", cand=["ep-1"])]))

        errors, _, gaps, counts = checks.v5(reps, EXTRACT)

        assert errors == [] and gaps == [] and counts["v5_open"] == 0

    def test_unknown_id_errors(self):
        errors, _, _, _ = checks.v5(reports(card("io.inputs", [row("env", "x", cand=["io-zzz"])])), EXTRACT)

        assert "V5: io card io.inputs names io-zzz, which is not a tool finding in this build." in errors

    def test_kept_and_dismissed_errors(self):
        reps = reports(card("io.inputs", [row("env", "x", cand=["io-1"])]), card("io.outputs", dismissed=[{"cand": ["iog-1"], "reason": "No."}]))

        errors, _, _, _ = checks.v5(reps, EXTRACT)

        assert "V5: io-1 is kept in io.inputs and dismissed in io.outputs." in errors

    def test_dismissal_without_reason_errors(self):
        errors, _, _, _ = checks.v5(reports(card("io.inputs", dismissed=[{"cand": ["io-1"], "reason": " "}])), EXTRACT)

        assert any("needs the finding ids" in e for e in errors)

    def test_cand_with_added_errors(self):
        errors, _, _, _ = checks.v5(reports(card("io.inputs", [row("env", "x", cand=["io-1"], added=True)])), EXTRACT)

        assert any("both which tool findings" in e for e in errors)

    def test_row_with_neither_warns(self):
        _, warnings, _, _ = checks.v5(reports(card("io.inputs", [row("env", "x")])), EXTRACT)

        assert warnings == ["V5: io card io.inputs, row 'env': say which tool findings it covers ('cand') or mark it 'added'."]

    def test_fixed_none_row_is_exempt(self):
        _, warnings, _, _ = checks.v5(reports(card("io.inputs", [row("stdin", "none", "-")])), EXTRACT)

        assert warnings == []

    def test_gap_items_have_fixed_statement_and_citation(self):
        _, _, gaps, _ = checks.v5({}, EXTRACT)

        first = next(g for g in gaps if g["report"] == "io" and "src/a.py" in g["statement"])
        assert first["statement"] == "A tool found 2 item(s) for Inputs in [[src/a.py:3]] (dossier.python.input.env-var) that no report accounts for."
        assert first["kind"] == "coverage" and first["how_to_confirm"].startswith("Decide in the report")

    def test_no_extract_reports_nothing(self):
        assert checks.v5(reports(card("io.inputs", [row("env", "x", cand=["io-1"])])), {}) == ([], [], [], {"v5_candidates": 0, "v5_open": 0})


class TestValidate:
    def test_malformed_card_does_not_crash(self):
        res = checks.validate({"io": {"cards": [{"card": "io.inputs", "blocks": "bad", "dismissed": 3}]}}, EXTRACT)

        assert set(res) == {"errors", "warnings", "gaps", "counts", "unbacked", "info"}


def entity(i, group, name, fields=()):
    return {"id": i, "group": group, "path": "src/models.py", "line": 3, "kind": "dataclass", "rule": "dataclass", "snippet": f"class {name}:",
            "name": name, "fields": [{"name": f, "type": "str", "line": 4, "ref": None} for f in fields]}


def ep(i, name, path, group="epg-2"):
    return {"id": i, "group": group, "path": path, "line": 1, "kind": "cli-command", "rule": "r.cli", "name": name}


MODELS = {"models": [entity("md-1", "mdg-1", "Config", ["path", "debug"]), entity("md-2", "mdg-1", "Settings", ["name"]), entity("md-3", "mdg-1", "Watch")],
          "entry_points": [ep("ep-1", "init", "cli.py"), ep("ep-2", "run", "cli.py"), ep("ep-3", "init", "cli.py", group="epg-3")]}


def entities_card(*rows, **kw):
    return {"card": "data.entities", "blocks": [{"type": "table", "columns": ["Name", "Kind", "Fields", "Defined in", "Owner component"], "rows": list(rows)}], **kw}


def entity_row(name, fields, **kw):
    return row(name, "dataclass", fields, "src/models.py", "Core", **kw)


class TestV5OneRowPerItem:
    def run(self, *cards, extract=None):
        errors, _, _, _ = checks.v5(reports(*cards), extract or MODELS)
        return errors

    def test_a_group_id_for_entities_is_an_error_naming_every_member(self):
        errors = self.run(entities_card(entity_row("Config and related", "path, debug", cand=["mdg-1"])))

        assert any("decides the group mdg-1" in e and "md-1, md-2, md-3" in e and "entity" in e for e in errors)

    def test_a_group_id_for_entry_points_is_an_error(self):
        errors = self.run(card("entry.catalog", [row("init", cand=["epg-2"])]))

        assert any("decides the group epg-2" in e and "ep-1, ep-2" in e and "entry point" in e for e in errors)

    def test_a_group_id_in_a_dismissal_of_entities_is_an_error(self):
        errors = self.run(entities_card(dismissed=[{"cand": ["mdg-1"], "reason": "Test doubles."}]))

        assert any("decides the group mdg-1" in e for e in errors)

    def test_two_entities_in_one_row_is_an_error_naming_them(self):
        errors = self.run(entities_card(entity_row("Config, Settings", "path, debug, name", cand=["md-1", "md-2"])))

        assert any("puts 2 entities in one row (Config, Settings); give each its own row." in e for e in errors)

    def test_an_entity_row_that_leaves_a_field_out_is_an_error_listing_it(self):
        errors = self.run(entities_card(entity_row("Config", "path", cand=["md-1"])))

        assert any("Config: the Fields cell leaves out debug." in e for e in errors)

    def test_a_field_name_inside_a_longer_word_does_not_count(self):
        errors = self.run(entities_card(entity_row("Settings", "username", cand=["md-2"])))

        assert any("Settings: the Fields cell leaves out name." in e for e in errors)

    def test_a_complete_one_to_one_row_passes(self):
        errors = self.run(entities_card(entity_row("Config", "`path`, `debug`", cand=["md-1"]), entity_row("Settings", "name", cand=["md-2"]),
                                        entity_row("Watch", "-", cand=["md-3"])))

        assert [e for e in errors if "Fields cell" in e or "one row" in e or "group" in e] == []

    def test_one_entry_point_found_twice_may_share_a_row(self):
        errors = self.run(card("entry.catalog", [row("init", cand=["ep-1", "ep-3"]), row("run", cand=["ep-2"])]))

        assert [e for e in errors if "one row" in e or "group" in e] == []

    def test_two_different_entry_points_in_one_row_is_an_error(self):
        errors = self.run(card("entry.catalog", [row("init and run", cand=["ep-1", "ep-2"])]))

        assert any("puts 2 entry points in one row (init, run)" in e for e in errors)

    def test_a_group_id_for_io_call_sites_still_passes(self):
        calls = {"io_candidates": [item("io-1", "iog-1"), item("io-2", "iog-1", line=9)]}

        errors = self.run(card("io.inputs", [row("env", "x", cand=["iog-1"])]), extract=calls)

        assert errors == []
