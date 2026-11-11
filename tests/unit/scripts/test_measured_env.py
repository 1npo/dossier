import re

import measured
import page_audit


class Refs:
    def mark(self, cites):
        return f"[{','.join(cites)}]"


FACTS = {"env_vars": [{"name": "APP_PORT", "count": 2, "first": {"path": "app.py", "line": 2},
                       "sites": [{"path": "app.py", "line": 2, "default": "80"}, {"path": "b.py", "line": 1}], "declared_in": ["Dockerfile"]},
                      {"name": "ONLY_ENV", "count": 1, "first": {"path": ".env.example", "line": 1}, "sites": [], "declared_in": [".env.example"]}],
         "secret_signals": {"hits": [{"path": "app.py", "line": 3, "kind": "github-token"}], "sensitive_files": [{"path": ".env", "verdict": "No secret-looking assignments found."}]}}


def ctx(facts=FACTS, files=None):
    files = files or {"app.py": "a\nb\nc\n", "b.py": "x\n", "Dockerfile": "FROM x\n", ".env": "A=1\n", ".env.example": "ONLY_ENV=1\n"}
    return {"facts": facts, "tree": set(files), "read": files.get, "extract": {}}


def rows(html):
    return re.findall(r"<tr><td", html)


class TestEnvCard:
    def test_one_row_per_variable_with_reads_default_and_declaration(self):
        html = measured.body("ops.env-vars", ctx(), Refs())

        assert 'id="t-ops-env-vars"' in html and len(rows(html)) == 2
        assert "80" in html and "Dockerfile" in html and "declared only" in html

    def test_every_row_is_listed_with_no_cap(self):
        many = {"env_vars": [{"name": f"V_{i}", "count": 1, "first": {"path": "a.py", "line": 1}, "sites": [{"path": "a.py", "line": 1}], "declared_in": []} for i in range(400)],
                "secret_signals": {"hits": [], "sensitive_files": []}}

        assert len(rows(measured.body("ops.env-vars", ctx(many), Refs()))) == 400

    def test_without_variables_the_table_is_drawn_empty_and_says_so(self):
        html = measured.body("ops.env-vars", ctx({"env_vars": [], "secret_signals": {}}), Refs())

        assert 'id="t-ops-env-vars"' in html and not rows(html)
        assert "No environment variable reads were found." in html

    def test_without_facts_the_card_falls_back_to_the_placeholder(self):
        assert measured.body("ops.env-vars", {"extract": {}}, Refs()) is None


class TestSecretCard:
    def test_the_first_line_says_it_is_not_a_scanner(self):
        html = measured.body("ops.secret-signals", ctx(), Refs())

        assert html.startswith('<p class="muted">This lists pattern matches for human review. It is not a security scanner')

    def test_rows_hold_path_line_and_pattern_for_matches_and_sensitive_files(self):
        html = measured.body("ops.secret-signals", ctx(), Refs())

        assert len(rows(html)) == 2 and "github-token" in html and "sensitive file name" in html and "[app.py:3]" in html

    def test_nothing_found_says_so(self):
        html = measured.body("ops.secret-signals", ctx({"env_vars": [], "secret_signals": {"hits": [], "sensitive_files": []}}), Refs())

        assert "none-found" in html and not rows(html)


class TestAudit:
    def page(self, c):
        return "".join(f'<div data-card="{cid}"><header><h3>x</h3></header>{measured.body(cid, c, Refs())}</div>' for cid in ("ops.env-vars", "ops.secret-signals"))

    def test_a_faithful_page_has_no_errors(self):
        c = ctx()

        assert page_audit._check_env_cards(cards_of(self.page(c)), c) == []

    def test_a_row_naming_a_missing_file_or_line_is_an_error(self):
        bad = {**FACTS, "env_vars": [{"name": "X", "count": 1, "first": {"path": "gone.py", "line": 1}, "sites": [{"path": "gone.py", "line": 1}, {"path": "b.py", "line": 9}], "declared_in": []}]}
        c = ctx(bad)

        errs = page_audit._check_env_cards(cards_of(self.page(c)), c)

        assert any("gone.py" in e and "not tracked" in e for e in errs) and any("b.py:9" in e and "1 lines" in e for e in errs)

    def test_a_dropped_row_is_an_error(self):
        c = ctx()
        page = self.page(c)
        short = {**FACTS, "env_vars": FACTS["env_vars"][:1]}

        errs = page_audit._check_env_cards(cards_of(page), ctx(short) | {"facts": FACTS | {"env_vars": FACTS["env_vars"] * 2}})

        assert any("ops.env-vars" in e and "has 2 rows, expected 4" in e for e in errs)


def cards_of(page):
    root = page_audit.parse(page)
    out = {}
    for n in root.walk():
        if "data-card" in n.attrs:
            out.setdefault(n.attrs["data-card"], []).append(n)
    return out
