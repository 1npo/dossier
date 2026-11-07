import functools
import json
import os
import subprocess
from pathlib import Path

import pytest

import js_api
import js_tools
import sandbox
from conftest import build_js_repo, line_of

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")

CODE = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")


@pytest.fixture(scope="module")
def tools(tmp_path_factory):
    base = tmp_path_factory.mktemp("tsfacts")
    area = base / "cache" / "repo"
    area.mkdir(parents=True)
    run = functools.partial(sandbox.run, area=area, cwd=base)
    install = js_tools.ensure_installed(functools.partial(run, timeout=900), area.parent, 900)
    return base, js_tools.TsFacts(run, install, 300)


@pytest.fixture(scope="module")
def shop(tools):
    base, client = tools
    repo = build_js_repo(base)
    files = [f for f in subprocess.run(["git", "ls-files"], cwd=repo.path, capture_output=True, text=True).stdout.split() if f.endswith(CODE)]
    return repo, client.facts(repo.path, files)


def _web(shop_facts):
    return {c["name"]: c for c in shop_facts["components"] if c["path"].startswith("packages/web/")}


class TestTsFactsTypes:
    def test_types_hold_the_fixture_models_with_exported_flags_and_field_lines(self, shop):
        repo, facts = shop

        types = {t["name"]: t for t in facts["types"] if t["path"] == "src/types.ts"}

        assert {n: types[n]["exported"] for n in ("Order", "Item", "Status", "ButtonProps", "Local")} == \
            {"Order": True, "Item": True, "Status": True, "ButtonProps": True, "Local": False}
        assert [(f["name"], f["optional"]) for f in types["Order"]["fields"]][-1] == ("note", True)
        assert types["Order"]["line"] == line_of(repo.path, "src/types.ts", "model-order")

    def test_a_decorated_class_lists_its_decorator(self, shop):
        _, facts = shop

        product = next(t for t in facts["types"] if t["name"] == "Product")

        assert product["decorators"] == ["Entity"] and product["kind"] == "class"


class TestTsFactsImportsAndExports:
    def test_a_type_only_import_is_marked_and_a_computed_dynamic_import_is_absent(self, shop):
        _, facts = shop

        up = next(i for i in facts["imports"] if i["path"] == "src/users/service.ts" and i["specifier"] == "../main")

        assert up["type_only"] is True
        assert not [i for i in facts["imports"] if i["path"] == "src/plugins.ts" and i["dynamic"]]

    def test_exports_hold_the_declared_names_of_a_file(self, shop):
        _, facts = shop

        names = {e["name"] for e in facts["exports"] if e["path"] == "src/a.ts"}

        assert "a" in names


class TestTsFactsReact:
    def test_app_renders_button_with_its_file_and_a_provider_is_recorded(self, shop):
        _, facts = shop

        web = _web(facts)

        assert {"name": "Button", "path": "packages/web/src/Button.tsx"} in web["App"]["renders"]
        assert web["CartProvider"]["provides"] == ["CartContext"]
        assert web["Home"]["hooks"] == ["useCart"]

    def test_routes_cover_literal_constant_computed_and_lazy(self, shop):
        repo, facts = shop

        routes = {r["line"]: r for r in facts["routes"]}
        literal = routes[line_of(repo.path, "packages/web/src/router.tsx", "ui-literal")]
        constant = routes[line_of(repo.path, "packages/web/src/router.tsx", "ui-constant")]
        computed = routes[line_of(repo.path, "packages/web/src/router.tsx", "ui-computed")]

        assert (literal["route"], literal["resolved"]) == ("/", True)
        assert (constant["route"], constant["resolved"]) == ("/cart", True)
        assert computed["resolved"] is False
        assert any(r["file"] == "packages/web/src/pages/Home.tsx" for r in facts["routes"])


class TestTsFactsConfig:
    def _run(self, tools, tmp_path, files, config):
        _, client = tools
        for rel, text in files.items():
            (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / rel).write_text(text)
        (tmp_path / "tsconfig.json").write_text(json.dumps(config))
        return client.facts(tmp_path, [f for f in files if f.endswith(CODE)])

    def test_references_without_paths_pick_the_referenced_config_that_has_paths(self, tools, tmp_path):
        (tmp_path / "tsconfig.app.json").write_text(json.dumps({"compilerOptions": {"paths": {"@/*": ["./src/*"]}}, "include": ["src"]}))

        facts = self._run(tools, tmp_path, {"src/a.ts": "export const a = 1;\n"}, {"files": [], "references": [{"path": "./tsconfig.app.json"}]})

        assert facts["config"]["used"] == "tsconfig.app.json" and facts["exports"][0]["name"] == "a"

    def test_a_missing_extends_is_reported_and_results_still_come(self, tools, tmp_path):
        facts = self._run(tools, tmp_path, {"src/a.ts": "export const a = 1;\n"}, {"extends": "@missing/base/tsconfig.json"})

        assert facts["errors"] and facts["exports"][0]["name"] == "a"


class TestTsFactsPublicApi:
    @pytest.fixture(name="api")
    def api_fixture(self, tools, shop):
        repo, _ = shop
        _, client = tools
        files = subprocess.run(["git", "ls-files"], cwd=repo.path, capture_output=True, text=True).stdout.split()
        code = [f for f in files if f.endswith(CODE)]
        read = lambda p: (Path(repo.path) / p).read_text()
        project = {"dir": "packages/lib", "manifest": json.loads(read("packages/lib/package.json"))}
        found = js_api.entries(project, files, js_api.read_tsconfig(read, "packages/lib/tsconfig.json"))
        facts = client.facts(repo.path, code, [{"entry": e["file"], "subpath": e["subpath"]} for e in found if e["file"]])
        return found, facts

    def test_the_library_lists_what_its_manifest_lets_a_sibling_import(self, api):
        _, facts = api

        names = {(a["subpath"], a["name"]) for a in facts["api"]}

        assert {(".", "sum"), (".", "double"), (".", "version"), (".", "deep"), ("./utils/fmt", "fmt")} <= names
        assert (".", "twice") not in names and (".", "hidden") not in names
        assert not [a for a in facts["api"] if (a["path"] or "").startswith("packages/lib/src/internal/")]

    def test_a_name_reached_through_two_star_hops_points_at_its_definition(self, api):
        _, facts = api

        deep = next(a for a in facts["api"] if a["name"] == "deep")

        assert (deep["path"], deep["kind"]) == ("packages/lib/src/deep.ts", "function")

    def test_a_renamed_export_keeps_the_public_name_and_the_definition_site(self, api):
        _, facts = api

        double = next(a for a in facts["api"] if a["name"] == "double")

        assert double["path"] == "packages/lib/src/math.ts"

    def test_a_star_export_of_a_missing_package_is_reported_not_lost(self, tools, tmp_path):
        _, client = tools
        (tmp_path / "index.ts").write_text("export * from 'not-installed';\nexport const ok = 1;\n")

        facts = client.facts(tmp_path, ["index.ts"], [{"entry": "index.ts", "subpath": "."}])

        assert [a["name"] for a in facts["api"]] == ["ok"]
        assert facts["api_unresolved"] == [{"entry": "index.ts", "subpath": ".", "specifier": "not-installed"}]
