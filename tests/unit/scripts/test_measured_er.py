import html as htmllib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent / "scripts"))

import measured  # noqa: E402
import measured_er  # noqa: E402
import repo_adapter  # noqa: E402


class Refs:
    def mark(self, cites):
        return ""


def ddl(name, columns, extra=""):
    lines = [f"  {c} TEXT" for c in columns]
    return f"CREATE TABLE {name} (\n" + ",\n".join(lines + ([extra] if extra else [])) + "\n);\n"


def sql_items():
    runs = ddl("runs", ["id", "started_at", "finished_at", "version"], "")
    runs = runs.replace("  id TEXT", "  id INTEGER PRIMARY KEY")
    scrapes = ddl("scrapes", ["id"] + [f"scrape_col_{i}" for i in range(11)] + ["run_id"])
    scrapes = scrapes.replace("  run_id TEXT", "  run_id INTEGER NOT NULL REFERENCES runs(id)").replace("  id TEXT", "  id INTEGER PRIMARY KEY")
    products = ddl("products", [f"product_col_{i}" for i in range(19)] + ["scrape_id"])
    products = products.replace("  scrape_id TEXT", "  scrape_id INTEGER NOT NULL REFERENCES scrapes(id)")
    episodes = ddl("alert_episodes", [f"episode_col_{i}" for i in range(9)])
    items = []
    for text in (runs, scrapes, products, episodes):
        items += repo_adapter.sql_tables("src/app/repository/schema.sql", text)
    return items


def model(name, path, fields, kind="dataclass"):
    return {"path": path, "line": 1, "name": name, "kind": kind, "bases": [],
            "fields": [{"name": n, "type": t, "line": 2 + i, "ref": ref} for i, (n, t, ref) in enumerate(fields)]}


PRODUCT = model("Product", "src/app/models.py", [(f"f{i}", "str", None) for i in range(19)])
ALERT = model("Alert", "src/app/alerts/state.py", [("product", "Product", "Product"), ("when", "datetime | None", None),
                                                    ("limits", "Mapping[str, float]", None)])


def field_rows(html):
    table = re.search(r'<table class="table[^"]*" id="t-data-relationships-fields".*?</table>', html, re.S).group(0)
    return [[htmllib.unescape(re.sub(r"</?[a-z][^>]*>", "", c)) for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
            for r in re.findall(r"<tr>(.*?)</tr>", table.split("<tbody>")[1], re.S)]


def sources(html):
    return [htmllib.unescape(s) for s in re.findall(r'class="mermaid-host"[^>]*data-src="([^"]*)"', html)]


PACKAGE = {"kind": "module", "path": "src/app/__init__.py", "module": "app", "package": "app", "is_package": True}


def ctx(models, catalog=None):
    return {"extract": {"models": models, "graph": [PACKAGE]}, "catalog": catalog or []}


class TestDrawnRelationships:
    def test_every_field_of_every_entity_is_in_the_field_table_and_the_diagram(self):
        html = measured.body("data.relationships", ctx(sql_items() + [PRODUCT]), Refs())

        assert len(field_rows(html)) == 46 + 19
        assert len([ln for src in sources(html) for ln in src.splitlines() if re.match(r"\s+\w+ \w+( PK| FK|, FK)*$", ln)]) == 46 + 19

    def test_foreign_keys_become_relations_from_the_referenced_table(self):
        html = measured.body("data.relationships", ctx(sql_items()), Refs())

        src = "\n".join(sources(html))
        assert re.search(r"runs \|\|--o\{ scrapes : \"run_id\"", src)
        assert re.search(r"scrapes \|\|--o\{ products : \"scrape_id\"", src)

    def test_keys_are_marked(self):
        html = measured.body("data.relationships", ctx(sql_items()), Refs())

        src = "\n".join(sources(html))
        assert "INTEGER id PK" in src
        assert "INTEGER run_id FK" in src

    def test_a_model_field_that_names_another_entity_is_a_relation(self):
        html = measured.body("data.relationships", ctx([PRODUCT, ALERT]), Refs())

        assert re.search(r"Alert \}o--\|\| Product : \"product\"", "\n".join(sources(html)))

    def test_types_with_spaces_and_bars_are_made_safe_and_the_table_keeps_the_original(self):
        html = measured.body("data.relationships", ctx([PRODUCT, ALERT]), Refs())

        src = "\n".join(sources(html))
        assert "datetime_or_None when" in src
        assert "Mapping_str_float limits" in src
        assert any(r[2] == "Mapping[str, float]" for r in field_rows(html))

    def test_migrations_are_not_entities(self):
        html = measured.body("data.relationships", ctx([PRODUCT, {"path": "db/migrations/1.sql", "kind": "migration"}]), Refs())

        assert [r[0] for r in field_rows(html)] == ["Product"] * 19

    def test_the_same_entity_found_twice_is_drawn_once(self):
        html = measured.body("data.relationships", ctx([PRODUCT, dict(PRODUCT)]), Refs())

        assert len(field_rows(html)) == 19

    def test_without_models_extracted_the_placeholder_is_used(self):
        assert measured.body("data.relationships", {"extract": {"graph": []}}, Refs()) is None

    def test_no_entities_says_so(self):
        assert "No entities were found." in measured.body("data.relationships", ctx([]), Refs())

    def test_a_small_set_is_one_diagram_not_marked_over_budget(self):
        html = measured.body("data.relationships", ctx([PRODUCT, ALERT]), Refs())

        assert len(sources(html)) == 1
        assert "data-budget" not in html


def big_models():
    items = []
    for c in range(6):
        for n in range(8):
            items.append(model(f"C{c}E{n}", f"src/app/comp{c}/m{n}.py", [("a", "str", None), ("b", "C%dE%d" % (c, n - 1) if n else "str", f"C{c}E{n - 1}" if n else None)]))
    other = model("Outside", "src/app/comp1/x.py", [("link", "C0E0", "C0E0")])
    return items + [other] + sql_items()


CATALOG = [{"name": f"Comp{c}", "paths": [f"src/app/comp{c}/"]} for c in range(6)] + [{"name": "Repository", "paths": ["src/app/repository/"]}]


class TestSplitByComponent:
    def test_more_than_twelve_entities_give_a_diagram_per_component_and_one_for_sql(self):
        html = measured.body("data.relationships", ctx(big_models(), CATALOG), Refs())

        titles = re.findall(r"<h4>(.*?)</h4>", html)
        assert titles == [f"Comp{c}" for c in range(6)] + ["SQL tables"]

    def test_the_field_table_still_lists_every_field(self):
        models = big_models()
        html = measured.body("data.relationships", ctx(models, CATALOG), Refs())

        assert len(field_rows(html)) == sum(len(m["fields"]) for m in models)

    def test_an_entity_a_relation_points_to_in_another_component_is_drawn_without_fields(self):
        html = measured.body("data.relationships", ctx(big_models(), CATALOG), Refs())

        comp1 = sources(html)[1]
        assert "C0E0" in comp1 and "(in Comp0)" in comp1
        assert comp1.count("C0E0") >= 2
        assert not re.search(r'C0E0\["[^"]*"\] \{[^}]*str', comp1)

    def test_diagrams_within_budget_are_not_marked_and_the_others_are(self):
        html = measured.body("data.relationships", ctx(big_models(), CATALOG), Refs())

        assert html.count('data-budget="area"') == 0
        assert all(len(re.findall(r"^\s+\w+\[", s, re.M)) <= 13 for s in sources(html))

    def test_without_a_catalog_the_split_is_by_area(self):
        html = measured.body("data.relationships", ctx(big_models()), Refs())

        titles = re.findall(r"<h4>(.*?)</h4>", html)
        assert "comp0" in titles and "SQL tables" in titles


class TestSafeNames:
    def test_a_column_that_starts_with_a_digit_gets_a_prefix(self):
        assert measured_er.safe_name("1st") == "f_1st"

    def test_punctuation_becomes_one_underscore(self):
        assert measured_er.safe_name("odd name!") == "odd_name"

    def test_an_empty_name_is_called_field(self):
        assert measured_er.safe_name("--") == "field"

    def test_bars_and_brackets_in_a_type_are_made_safe(self):
        assert [measured_er.safe_type(t) for t in ("str | None", "Mapping[str, float]", "Callable[[int], str]", "", "3d")] == [
            "str_or_None", "Mapping_str_float", "Callable_int_str", "any", "t_3d"]
