import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import summary  # noqa: E402
import summary_check  # noqa: E402

NOW = "2026-11-05T10:00:00Z"
ANN, BOB, BOT = "ann@users.noreply.github.com", "bob@example.org", "ci@example.org"


def person(ident, name, kind="human", aliases=(), commits=3, owned_lines=0, username=None):
    return {"kind": "person", "path": "", "person": ident, "name": name, "type": kind, "commits": commits, "commits_12m": commits,
            "aliases": list(aliases), "owned_commits": commits, "owned_lines": owned_lines, "username": username}


def file_item(path, commits_12m, owner_lines):
    return {"kind": "file", "path": path, "commits_12m": commits_12m, "authors": {}, "blame": {}, "owner_lines": owner_lines}


def table(cid, columns, *rows):
    return {"card": cid, "blocks": [{"type": "table", "columns": columns, "rows": [{"cells": list(r), "conf": "confirmed", "cite": ["src/app/main.py:4"]} for r in rows]}]}


def reports(**over):
    r = {
        "components": {"cards": [table("components.catalog", ["Component", "Paths"], ("`App`", "src/app/"), ("`Db`", "src/db/"))]},
        "entry": {"cards": [table("entry.catalog", ["Kind", "Name", "Triggered by", "Starts at", "Notes"], ("CLI", "`app` [[src/app/main.py:4]]", "user", "src/app/main.py", "-"))]},
        "io": {"cards": [table("io.contracts", ["Contract", "Direction", "Counterparty", "Schema location", "Versioning"],
                               ("Orders API", "Offered", "billing", "[[schemas/orders.json]]", "v1"), ("Stripe", "consumed", "stripe", "-", "-"))]},
        "data": {"cards": [table("data.stores", ["Store", "Technology", "Holds", "Migration approach"], ("main db", "PostgreSQL", "orders", "alembic"))]},
        "contributors": {"cards": [table("contributors.concentration", ["Area", "Owner", "Share", "Status"], ("App", "Ann", "-", "departed"), ("Db", "Bob", "-", "shared"))]},
        "risks": {"cards": [table("risks.tracker", ["ID", "Risk", "Category", "Severity", "Impact", "Recommendation", "Source"],
                                  ("R1", "x", "c", "High", "i", "r", "read"), ("R2", "y", "c", "Low", "i", "r", "extractor"))]},
    }
    r.update(over)
    return r


EXTRACT = {
    "history": [{"kind": "meta", "path": "", "status": "ok"},
                person(ANN, "Ann", aliases=["ann@old.org"], owned_lines=60), person(BOB, "Bob", owned_lines=40), person(BOT, "ci@example.org", "bot", owned_lines=500),
                person("github:zed", "zed", commits=0),
                file_item("src/app/main.py", 5, {ANN: 60, "ann@old.org": 20, BOT: 100}), file_item("src/db/store.py", 2, {BOB: 40}), file_item("src/db/old.py", 0, {})],
    "entry_points": [{"id": "ep-1", "group": "epg-1", "path": "src/app/main.py", "line": 9, "kind": "main-guard"}],
    "graph": [{"kind": "module", "path": "src/app/main.py", "module": "app.main"}, {"kind": "module", "path": "src/db/store.py", "module": "db.store"},
              {"kind": "import", "path": "src/app/main.py", "paths": ["src/db/store.py"], "from": "app.main", "to": "db.store", "lines": [1]}],
}
FACTS = {"repo": {"name": "shop", "remote": {"url": "git@github.com:o/shop.git", "web_base": "https://github.com/o/shop"}, "branch": "main", "sha": "a" * 40, "commit_date": "2026-11-01"},
         "languages": [{"name": "Python", "kind": "code", "share_pct": 90.0}, {"name": "JSON", "kind": "data", "share_pct": 10.0}],
         "file_lines": {"src/app/main.py": 100, "src/db/store.py": 40, "src/db/old.py": 10}}
DEPS = {"deps": [{"n": "requests", "ecosystem": "python", "s": "runtime", "src": 3, "tst": 1}, {"n": "pytest", "ecosystem": "python", "s": "dev", "src": 0, "tst": 5}],
        "unused": [{"n": "left-pad", "s": "runtime", "ecosystem": "node", "note": "x"}]}
TREE = {"src/app/main.py", "src/db/store.py", "src/db/old.py"}
TOOLS = [{"name": "git", "version": "2.47", "status": "ok", "reason": None}, {"name": "vulture", "version": "2.14", "status": "failed", "reason": "x"},
         {"name": "knip", "version": "", "status": "skipped", "reason": "y"}]


def make(rep=None, extract=None, **kw):
    return summary.build(FACTS, rep if rep is not None else reports(), extract if extract is not None else EXTRACT, None,
                         {"unknown": 1, "inference": 2, "assumption": 3, "coverage": 4}, "0.8.0", DEPS, TREE, tools=TOOLS, now=NOW, **kw)


class TestPlain:
    @pytest.mark.parametrize("cell,want", [("`app` [[src/a.py:4]]", "app"), ("see [[src/a.py:4|the file]] here", "see the file here"), ("  a   b ", "a b"), (None, "")])
    def test_citations_are_dropped_and_labels_kept(self, cell, want):
        assert summary.plain(cell) == want


class TestBuild:
    def test_the_document_validates_against_the_schema(self):
        assert summary.validate(make()) == []

    def test_header_and_repo(self):
        doc = make()

        assert (doc["schema_version"], doc["dossier_version"], doc["generated_at"]) == (1, "0.8.0", NOW)
        assert doc["repo"] == {"name": "shop", "remote": "https://github.com/o/shop", "branch": "main", "sha": "a" * 40, "commit_date": "2026-11-01"}

    def test_only_code_languages_are_listed_and_tier_defaults_to_b(self):
        assert make()["languages"] == [{"name": "Python", "tier": "B", "share": 90.0}]

    def test_extractor_status_follows_the_tool_status(self):
        got = {e["name"]: e["status"] for e in make()["extractors"]}

        assert got == {"git": "ok", "knip": "missing", "vulture": "partial"}

    def test_partial_history_makes_git_partial(self):
        extract = {**EXTRACT, "history": [{"kind": "meta", "status": "partial"}, *EXTRACT["history"][1:]]}

        assert {e["name"]: e["status"] for e in make(extract=extract)["extractors"]}["git"] == "partial"

    def test_components_have_ids_edges_sizes_and_owners_of_at_least_twenty_percent(self):
        app, db = make()["components"]

        assert (app["id"], app["paths"], app["size"], app["depends_on"], app["used_by"]) == ("app", ["src/app/"], 100, ["db"], [])
        assert (db["id"], db["size"], db["used_by"], db["depends_on"]) == ("db", 50, ["app"], [])
        ids = {c["name"]: c["id"] for c in make()["contributors"]}
        assert db["owners"] == [summary.contributor_id(BOB)] and ids["Bob"] == db["owners"][0]
        assert app["owners"] == sorted([summary.contributor_id(ANN), summary.contributor_id(BOT)])

    def test_entry_points_take_the_location_of_the_first_candidate(self):
        rep = reports(entry={"cards": [{**table("entry.catalog", ["Kind", "Name", "Triggered by", "Starts at", "Notes"], ("CLI", "app", "u", "x.py", "-")),
                                        }]})
        rep["entry"]["cards"][0]["blocks"][0]["rows"][0]["cand"] = ["ep-1"]

        assert make(rep)["entry_points"] == [{"kind": "CLI", "name": "app", "location": "src/app/main.py:9"}]

    def test_entry_points_fall_back_to_the_first_citation(self):
        assert make()["entry_points"] == [{"kind": "CLI", "name": "app", "location": "src/app/main.py:4"}]

    def test_contracts_lower_case_the_direction_and_find_the_schema_file(self):
        assert make()["contracts"] == [
            {"name": "Orders API", "direction": "offered", "counterparty": "billing", "schema_path": "schemas/orders.json"},
            {"name": "Stripe", "direction": "consumed", "counterparty": "stripe", "schema_path": None}]

    def test_dependencies_include_unused_ones_with_no_importing_files(self):
        assert make()["external_dependencies"] == [
            {"name": "requests", "ecosystem": "python", "scope": "runtime", "files_importing": 4},
            {"name": "pytest", "ecosystem": "python", "scope": "dev", "files_importing": 5},
            {"name": "left-pad", "ecosystem": "node", "scope": "runtime", "files_importing": 0}]

    def test_stores_risks_and_gaps(self):
        doc = make()

        assert doc["data_stores"] == [{"name": "main db", "technology": "PostgreSQL"}]
        assert doc["risks"] == {"critical": 0, "high": 1, "medium": 0, "low": 1, "info": 0}
        assert doc["gaps"] == {"unknown": 1, "inference": 2, "assumption": 3, "coverage": 4}

    def test_ownership_counts_humans_only_and_at_risk_paths_are_the_departed_components(self):
        assert make()["ownership"] == {"bus_factor": 1, "top_owner_share": 60, "at_risk_paths": ["src/app/"]}

    def test_hotspots_list_every_file_that_changed_in_the_window(self):
        assert make()["change"]["hotspots"] == [{"path": "src/app/main.py", "churn": 5}, {"path": "src/db/store.py", "churn": 2}]


class TestNotApplicable:
    def test_na_cards_give_empty_lists(self):
        na = lambda cid: {"card": cid, "na": "none", "cite": ["a.py"]}  # noqa: E731
        rep = reports(entry={"cards": [na("entry.catalog")]}, io={"cards": [na("io.contracts")]}, data={"cards": [na("data.stores")]})

        doc = make(rep)

        assert doc["entry_points"] == doc["contracts"] == doc["data_stores"] == []
        assert summary.validate(doc) == []

    def test_no_history_gives_null_ownership_and_empty_lists_but_keeps_departed_paths(self):
        doc = make(extract={})

        assert doc["ownership"] == {"bus_factor": None, "top_owner_share": None, "at_risk_paths": ["src/app/"]}
        assert doc["contributors"] == [] and doc["change"] == {"hotspots": [], "cochange_pairs_unlinked": 0}
        assert summary.validate(doc) == []


class TestContributors:
    def test_one_object_per_person_with_kind_name_and_username(self):
        got = {c["name"]: c for c in make()["contributors"]}

        assert set(got) == {"Ann", "Bob", "ci", "zed"}
        assert (got["Ann"]["kind"], got["Ann"]["username"]) == ("human", "ann")
        assert (got["ci"]["kind"], got["ci"]["username"]) == ("bot", None)
        assert got["zed"]["username"] == "zed"

    def test_an_explicit_username_wins(self):
        extract = {"history": [{"kind": "meta"}, person(BOB, "Bob", username="bobr")]}

        assert make(extract=extract)["contributors"][0]["username"] == "bobr"

    def test_ids_are_opaque_and_stable(self):
        ids = [c["id"] for c in make()["contributors"]]

        assert all(i.startswith("c-") and len(i) == 14 for i in ids) and ids == sorted(ids)
        assert summary.contributor_id(BOB) == summary.contributor_id(BOB) != summary.contributor_id(ANN)

    def test_every_owner_is_a_contributor_id(self):
        doc = make()
        known = {c["id"] for c in doc["contributors"]}

        assert all(o in known for c in doc["components"] for o in c["owners"])

    def test_no_email_address_appears_in_the_file(self):
        assert "@" not in json.dumps(make())


class TestAtRisk:
    def test_only_departed_components_count(self):
        rep = reports(contributors={"cards": [table("contributors.concentration", ["Area", "Owner", "Share", "Status"],
                                                    ("App", "Ann", "-", "shared"), ("Db", "Bob", "-", "single owner"))]})

        assert make(rep)["ownership"]["at_risk_paths"] == []


class TestValidate:
    def test_a_bad_direction_gives_one_line(self):
        rep = reports(io={"cards": [table("io.contracts", ["Contract", "Direction", "Counterparty", "Schema location", "Versioning"], ("X", "both", "y", "-", "-"))]})

        assert summary.validate(make(rep)) == ["V8: summary.json: $.contracts[0].direction: must be one of offered, consumed, found 'both'."]

    def test_a_missing_required_key_gives_one_line(self):
        doc = make()
        del doc["repo"]["sha"]

        assert summary.validate(doc) == ["V8: summary.json: $.repo: the key sha is missing."]

    def test_an_extra_key_is_not_allowed(self):
        doc = make()
        doc["gaps"]["extra"] = 1

        assert summary.validate(doc) == ["V8: summary.json: $.gaps: the key extra is not allowed."]

    def test_a_wrong_type_is_named(self):
        doc = make()
        doc["components"][0]["size"] = "big"

        assert summary.validate(doc) == ["V8: summary.json: $.components[0].size: must be integer."]

    def test_a_negative_count_is_below_the_minimum(self):
        doc = make()
        doc["risks"]["high"] = -1

        assert summary.validate(doc) == ["V8: summary.json: $.risks.high: must be at least 0."]

    def test_a_keyword_the_validator_does_not_implement_raises(self):
        with pytest.raises(ValueError, match="pattern"):
            summary.validate({"a": "x"}, {"type": "object", "properties": {"a": {"type": "string", "pattern": "^y"}}})

    def test_the_shipped_schema_uses_only_implemented_keywords(self):
        assert summary.validate({}, summary.load_schema())  # would raise on an unknown keyword

    def test_a_boolean_is_not_an_integer(self):
        assert summary.validate(True, {"type": "integer"}) == ["V8: summary.json: $: must be integer."]


class TestWrite:
    def test_write_then_remove(self, tmp_path):
        path = summary.write(tmp_path, {"a": 1})

        assert json.loads(path.read_text()) == {"a": 1} and not list(tmp_path.glob("*.tmp"))
        summary.remove(tmp_path)
        assert not path.exists()
        summary.remove(tmp_path)
