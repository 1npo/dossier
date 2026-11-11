import json

import env_scan
from test_gather_env import make_repo

import gather

FAKE_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"          # shaped like a key, assembled so no scanner flags this file
FAKE_GH = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"


def by_name(src):
    out = {}
    for s in env_scan.reads(src):
        out.setdefault(s["name"], []).append(s)
    return out


class TestPython:
    def test_every_read_form_is_found_with_its_line(self):
        got = by_name('import os\nos.environ["A_ONE"]\nos.environ.get("A_TWO")\nos.getenv("A_THREE")\n')

        assert {n: s[0]["line"] for n, s in got.items()} == {"A_ONE": 2, "A_TWO": 3, "A_THREE": 4}

    def test_literal_defaults_are_kept(self):
        got = by_name('os.environ.get("P", "8080")\nos.getenv("H", \'localhost\')\nos.getenv("N", 5)\nos.getenv("O") or "x"\nos.getenv("D", compute())\n')

        assert got["P"][0]["default"] == "8080" and got["H"][0]["default"] == "localhost" and got["N"][0]["default"] == "5"
        assert got["O"][0]["default"] == "x"
        assert "default" not in got["D"][0]

    def test_lowercase_and_short_names_are_found(self):
        assert set(by_name('os.getenv("http_proxy")\nos.getenv("X")\n')) == {"http_proxy", "X"}


class TestJavaScript:
    def test_process_env_and_import_meta_env(self):
        got = by_name('const a = process.env.API_URL;\nconst b = process.env["B_KEY_X"];\nconst c = import.meta.env.VITE_MODE;\nDeno.env.get("D_VAR");\n')

        assert set(got) == {"API_URL", "B_KEY_X", "VITE_MODE", "D_VAR"}

    def test_defaults_after_or_and_nullish(self):
        got = by_name('const p = process.env.PORT || 3000;\nconst h = process.env.HOST ?? "0.0.0.0";\nconst q = parseInt(process.env.Q) || 7;\n')

        assert [got[n][0]["default"] for n in ("PORT", "HOST", "Q")] == ["3000", "0.0.0.0", "7"]


class TestCSharp:
    def test_get_environment_variable_with_a_literal_name(self):
        got = by_name('var a = Environment.GetEnvironmentVariable("DB_HOST") ?? "db";\nvar n = "X";\nvar b = Environment.GetEnvironmentVariable(n);\n')

        assert set(got) == {"DB_HOST"} and got["DB_HOST"][0]["default"] == "db"


class TestWithheldDefaults:
    def test_a_default_under_a_secret_like_name_is_not_kept(self):
        got = by_name('os.environ.get("API_TOKEN", "hunter2-hunter2")\n')

        assert got["API_TOKEN"][0]["default"].startswith("(withheld")
        assert "hunter2" not in json.dumps(got)

    def test_a_default_shaped_like_a_credential_is_not_kept(self):
        got = by_name(f'os.environ.get("REGION_X", "{FAKE_AWS}")\n')

        assert FAKE_AWS not in json.dumps(got)


class TestSecrets:
    def test_every_match_is_listed_not_one_per_pattern(self):
        text = f"a = '{FAKE_AWS}'\nb = '{FAKE_AWS}'\nc = '{FAKE_GH}'\n"

        assert env_scan.secrets(text) == [{"line": 1, "kind": "aws-access-key-id"}, {"line": 2, "kind": "aws-access-key-id"}, {"line": 3, "kind": "github-token"}]

    def test_the_value_is_not_in_the_result(self):
        assert FAKE_GH not in json.dumps(env_scan.secrets(f"t = '{FAKE_GH}'\n"))


class TestGatherer:
    def test_sites_defaults_and_declarations(self, tmp_path):
        repo = make_repo(tmp_path, 'import os\nPORT = os.environ.get("APP_PORT", "80")\nos.getenv("APP_PORT")\n')
        (repo / "Dockerfile").write_text("FROM x\nENV APP_PORT=8080\n")
        import subprocess
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=A", "-c", "user.email=a@x.io", "commit", "-qm", "d"], check=True)

        facts, _ = gather.collect(str(repo))
        row = next(v for v in facts["env_vars"] if v["name"] == "APP_PORT")

        assert [(s["path"], s["line"]) for s in row["sites"]] == [("app.py", 2), ("app.py", 3)]
        assert row["sites"][0]["default"] == "80" and row["declared_in"] == ["Dockerfile"]

    def test_all_matches_are_kept_and_no_value_is_stored(self, tmp_path):
        src = "".join(f"K{i} = '{FAKE_AWS}'\n" for i in range(250))
        facts, _ = gather.collect(str(make_repo(tmp_path, src)))

        assert len(facts["secret_signals"]["hits"]) == 250
        assert FAKE_AWS not in json.dumps(facts)
