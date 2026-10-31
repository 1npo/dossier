import json

import deps


class FakeRepo:
    def __init__(self, blobs):
        self.blobs = blobs

    def read(self, oid):
        return "blob", self.blobs[oid].encode()


def run(tree):
    """analyze() over a dict of path -> text, standing in for the files at a commit."""
    entries = [(p, "blob", p, len(t)) for p, t in tree.items()]
    files = [{"path": p, "blob": p, "bytes": len(t)} for p, t in tree.items()]
    return deps.analyze(FakeRepo(tree), entries, files)


def dep(out, name):
    return next(d for d in out["deps"] if d["n"] == name)


PYPROJECT = """[project]
name = "app"
dependencies = ["PyYAML>=6", "requests", "unused-lib"]
[dependency-groups]
dev = ["pytest", "ruff"]
[tool.ruff]
line-length = 100
"""


class TestPython:
    def tree(self):
        return {"pyproject.toml": PYPROJECT,
                "src/app/main.py": "import yaml\nimport os\nfrom app import util\nimport requests\nrequests.get('x')\nimport semver\n",
                "src/app/util.py": "import yaml\n",
                "tests/test_main.py": "import pytest\nfrom app.main import x\n"}

    def test_import_names_resolve_to_distribution_names(self):
        out = run(self.tree())
        assert dep(out, "PyYAML")["src"] == 2 and dep(out, "requests")["sym"] == 1

    def test_stdlib_and_own_code_are_not_dependencies(self):
        out = run(self.tree())
        assert {u["n"] for u in out["undeclared"]} == {"semver"}

    def test_unused_excludes_tooling_used_through_configuration(self):
        out = run(self.tree())
        assert [u["n"] for u in out["unused"]] == ["unused-lib"]
        assert out["configOnly"] == {"runtime": 0, "dev": 1}

    def test_test_files_are_counted_apart_and_scope_follows_the_group(self):
        d = dep(run(self.tree()), "pytest")
        assert (d["src"], d["tst"], d["s"], d["group"]) == (0, 1, "dev", "dev")

    def test_inline_script_metadata_declares_dependencies(self):
        out = run({"tool.py": "# /// script\n# dependencies = [\"rich\"]\n# ///\nimport rich\n"})
        assert dep(out, "rich")["group"] == "script" and not out["undeclared"]

    def test_lockfile_gives_versions_and_transitive_chain(self):
        lock = 'version = 1\n[[package]]\nname = "requests"\nversion = "2.1"\ndependencies = [{ name = "urllib3" }]\n[[package]]\nname = "urllib3"\nversion = "2.0"\n'
        tree = {"pyproject.toml": '[project]\nname="a"\ndependencies=["requests"]\n', "uv.lock": lock, "a.py": "import requests, urllib3\n"}
        out = run(tree)
        assert dep(out, "requests")["v"] == "2.1" and dep(out, "requests")["tr"] == 1 and out["transTotal"] == 2
        assert out["undeclared"][0]["via"] == "requests → urllib3"


class TestJavaScript:
    def tree(self):
        return {"package.json": json.dumps({"name": "root", "dependencies": {"react": "^18", "left-pad": "1"}, "devDependencies": {"vitest": "2", "@types/node": "20"}}),
                "src/app.tsx": "import React, {useState} from 'react';\nimport {z} from 'zod/v4';\nimport fs from 'node:fs';\nimport x from './x';\nconst a = React.memo;\n",
                "src/app.test.tsx": "import {describe} from 'vitest';\nimport {render} from 'react';\n",
                "index.html": "<script src=\"https://cdn.jsdelivr.net/npm/dayjs@1/dayjs.min.js\"></script>"}

    def test_subpath_imports_and_builtins(self):
        out = run(self.tree())
        assert {u["n"] for u in out["undeclared"]} == {"zod", "dayjs"}
        assert dep(out, "react")["src"] == 1 and dep(out, "react")["tst"] == 1
        assert dep(out, "react")["sym"] == 3      # useState, render, memo

    def test_unused_and_type_packages(self):
        out = run(self.tree())
        assert [u["n"] for u in out["unused"]] == ["left-pad"]
        assert out["configOnly"]["dev"] == 1      # @types/node

    def test_runtime_package_used_only_in_tests_is_visible_in_the_data(self):
        out = run({"package.json": json.dumps({"dependencies": {"msw": "1"}}), "a.test.js": "import 'msw'\n"})
        d = dep(out, "msw")
        assert d["s"] == "runtime" and d["src"] == 0 and d["tst"] == 1


class TestCSharp:
    def test_namespaces_map_to_package_ids(self):
        out = run({"App/App.csproj": '<Project><ItemGroup><PackageReference Include="Newtonsoft.Json" Version="13.0.1" /><PackageReference Include="Serilog.AspNetCore" Version="8" /></ItemGroup></Project>',
                   "App/P.cs": "using System;\nusing Newtonsoft.Json.Linq;\nusing App.Models;\nusing Dapper;\nnamespace App.Models {}\n",
                   "App.Tests/App.Tests.csproj": '<Project><ItemGroup><PackageReference Include="xunit" Version="2" /></ItemGroup></Project>',
                   "App.Tests/T.cs": "using Xunit;\n"})
        assert dep(out, "Newtonsoft.Json")["sym"] == 1 and dep(out, "xunit")["tst"] == 1 and dep(out, "xunit")["s"] == "dev"
        assert [u["n"] for u in out["undeclared"]] == ["Dapper"] and [u["n"] for u in out["unused"]] == ["Serilog.AspNetCore"]


class TestShell:
    def test_declared_system_packages_are_matched_to_the_commands_called(self):
        out = run({"setup.sh": "apt-get install -y curl jq\ncurl -fsSL x | tar x\nrm -f y\n"})
        assert dep(out, "curl")["src"] == 1 and [u["n"] for u in out["unused"]] == ["jq"] and not out["undeclared"]


class TestOutput:
    def test_categories_come_from_a_fixed_list_and_unknown_is_other(self):
        assert deps.category("react") == "Framework" and deps.category("pytest-cov") == "Testing" and deps.category("zzz-unknown") == "Other"

    def test_nothing_declared_or_imported_gives_none(self):
        assert run({"README.md": "hi"}) is None

    def test_modules_follow_the_nearest_manifest(self):
        out = run({"packages/api/package.json": '{"dependencies":{"zod":"1"}}', "packages/api/src/a.ts": "import 'zod'", "packages/web/package.json": "{}", "packages/web/src/b.ts": "export {}"})
        assert {m["id"] for m in out["modules"]} == {"api", "web"} and dep(out, "zod")["mods"] == {"api": 1}


class TestCard:
    def test_card_has_tiles_findings_controls_and_escaped_data(self):
        import render
        out = run({"package.json": json.dumps({"dependencies": {"left-pad": "1", "msw": "1"}}), "a.test.js": "import 'msw'\nimport '</script>x'\n"})
        html = render.dependencies_card(out, type("R", (), {"mark": lambda s, c: ""})())
        assert "Declared, never imported" in html and "Runtime, used only in tests" in html and 'id="dp-view"' in html
        assert "</script>x" not in html and 'role="combobox"' in html

    def test_missing_data_says_to_run_prepare_again(self):
        import render
        assert "Run prepare again" in render.panel_dependencies({}, None)
