from dossier.findings import candidates
from dossier.adapters.csharp import adapter as cs_adapter
from dossier.render.measured import tables as measured_tables


def row(path, line, rule, detail, category="config-key"):
    return {"path": path, "line": line, "end_line": line, "rule": rule, "snippet": "x", "category": category, "detail": detail}


KEY, BIND = "dossier.csharp.config.config-key", "dossier.csharp.config.config-binding"


class TestGrouping:
    def test_one_row_per_name_and_kind_with_every_site(self):
        extract = {"io_candidates": [row("b.cs", 9, KEY, "Shop"), row("a.cs", 2, KEY, "Shop"), row("a.cs", 5, BIND, "ShopOptions"), row("a.cs", 5, KEY, "Shop")]}

        assert measured_tables.config_key_rows(extract) == [("Shop", "key", [("a.cs", 2), ("a.cs", 5), ("b.cs", 9)]), ("ShopOptions", "options class", [("a.cs", 5)])]

    def test_other_categories_are_ignored(self):
        assert measured_tables.config_key_rows({"io_candidates": [row("a.cs", 1, "x", "SHOP_KEY", category="env-var")]}) == []

    def test_a_name_missing_falls_back_to_the_snippet(self):
        assert measured_tables.config_key_rows({"io_candidates": [{**row("a.cs", 1, BIND, None), "snippet": "config.Bind(o)"}]})[0][0] == "config.Bind(o)"


class TestPage:
    def test_nothing_is_drawn_without_config_keys(self):
        assert measured_tables.config_keys({"extract": {"io_candidates": []}}, None) == ""
        assert measured_tables.config_keys({}, None) == ""


class TestCandidates:
    def test_the_writer_is_not_asked_to_decide_about_config_keys(self):
        item = row("a.cs", 1, KEY, "Shop")

        assert candidates.home_card("io_candidates", item) is None
        assert "config-key" in candidates.DRAWN_CATEGORIES and "config-key" not in candidates.CATEGORY_CARD

    def test_other_inputs_still_go_to_the_inputs_card(self):
        assert candidates.home_card("io_candidates", row("a.cs", 1, "x", "SHOP_KEY", category="env-var")) == "io.inputs"


def test_the_adapter_version_was_bumped():
    assert cs_adapter.CSharpAdapter.version == "4"
