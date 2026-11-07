import json
import os

import pytest

import buildlog
import stages
import workarea
from conftest import build_js_repo

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")


@pytest.fixture(scope="module")
def ex(tmp_path_factory):
    """One extraction of the JavaScript fixture repository with the adapter frame (the tool steps are not built yet)."""
    base = tmp_path_factory.mktemp("jsadapter")
    patch = pytest.MonkeyPatch()
    patch.setenv("DOSSIER_HOME", str(base / "home"))
    patch.setenv("DOSSIER_CONFIG", str(base / "cfg.json"))
    patch.setenv("DOSSIER_CACHE", str(base / "cache"))
    try:
        repo = build_js_repo(base)
        out = base / "home" / "jsrepo"
        area = workarea.area_for("jsrepo", repo.path, repo.sha, base / "cache")
        checkout = workarea.ensure_checkout(area, repo.path, repo.sha)["path"]
        build = buildlog.start(out, repo="jsrepo", sha=repo.sha, ref="main", version="test", options={})
        record = stages.stage_extract(build, repo.path, repo.sha, area, out, ["TypeScript", "JavaScript", "JSON"],
                                      workarea.trusted(repo.path, repo.sha), stages.Options(no_restore=True), {},
                                      stages.tree_at(repo.path, repo.sha), checkout)
        yield repo, out, record
    finally:
        patch.undo()


class TestJsAdapterFrame:
    def test_entry_points_have_a_js_section_with_the_package_entries(self, ex):
        repo, out, record = ex

        data = json.loads((out / "extract" / "entry_points.json").read_text())
        items = data["adapters"]["js"]["items"]

        assert record["status"] == "ok" and "js" in data["adapters"]
        bin_item = next(i for i in items if i["kind"] == "package-bin")
        assert (bin_item["name"], bin_item["path"], bin_item["id"].startswith("ep-")) == ("shopjs", "package.json", True)
        assert {"nx-target", "package-script", "http-route"} <= {i["kind"] for i in items}

    def test_the_adapter_records_a_status_for_every_tool(self, ex):
        _, _, record = ex

        js = next(a for a in record["details"]["adapters"] if a["name"] == "js")

        assert set(js["tools"]) == {"dependency-cruiser", "knip", "scip-typescript", "typescript", "semgrep", "tree-sitter-language-pack"}
        assert js["tools"]["typescript"]["status"] == "ok" and js["tools"]["dependency-cruiser"]["status"] == "ok"

    def test_the_graph_has_the_cycle_the_broken_rule_and_no_test_modules(self, ex):
        _, out, _ = ex

        graph = json.loads((out / "extract" / "graph.json").read_text())["adapters"]["js"]["items"]

        cycles = [i["modules"] for i in graph if i["kind"] == "cycle"]
        assert cycles == [["src/a", "src/b"]]
        assert not [i for i in graph if i["kind"] == "module" and "test" in i["path"]]
        contract = next(i for i in graph if i["kind"] == "contract")
        assert contract["status"] == "broken" and contract["violations"][0]["path"] == "src/users/service.ts"
        assert any(i["kind"] == "import" and i["to"] == "src/a" and i["from"] == "src/barrel/index" for i in graph)

    def test_knip_lists_the_unused_file(self, ex):
        _, out, record = ex

        dead = json.loads((out / "extract" / "dead.json").read_text())["adapters"]["js"]["items"]
        js = next(a for a in record["details"]["adapters"] if a["name"] == "js")

        assert js["tools"]["knip"]["status"] == "ok"
        assert any(d["type"] == "unused file" and d["path"] == "src/unused.ts" for d in dead)

    def test_models_hold_prisma_and_typescript_entities_but_not_props_or_local(self, ex):
        _, out, _ = ex

        models = json.loads((out / "extract" / "models.json").read_text())["adapters"]["js"]["items"]
        kinds = {(m["name"], m["kind"]) for m in models}

        assert {("User", "prisma"), ("Post", "prisma"), ("Role", "prisma-enum"), ("Order", "ts-interface"), ("Item", "ts-type"),
                ("Status", "ts-enum"), ("Product", "typeorm")} <= kinds
        assert not {"ButtonProps", "Local"} & {m["name"] for m in models}

    def test_react_components_renders_and_routes_are_recorded(self, ex):
        _, out, _ = ex

        graph = json.loads((out / "extract" / "graph.json").read_text())["adapters"]["js"]["items"]
        entries = json.loads((out / "extract" / "entry_points.json").read_text())["adapters"]["js"]["items"]

        assert any(g["kind"] == "renders" and g["from"] == "App" and g["to"] == "Button" for g in graph)
        assert {e["name"] for e in entries if e["kind"] == "ui-route"} == {"/", "/cart", "/home", "prefix + '/x'"}

    def test_the_library_public_api_is_reported_with_its_audience(self, ex):
        _, out, _ = ex

        symbols = json.loads((out / "extract" / "symbols.json").read_text())["adapters"]["js"]["items"]
        api = {(s["package"], s["subpath"], s["name"]) for s in symbols if s["kind"] == "public-api"}

        assert {("@shopjs/lib", ".", "sum"), ("@shopjs/lib", ".", "double"), ("@shopjs/lib", ".", "deep"), ("@shopjs/lib", "./utils/fmt", "fmt")} <= api
        assert not [a for a in api if a[2] in ("hidden", "twice")]
        assert not [a for a in api if a[0] == "@shopjs/web"]

    def test_semgrep_finds_the_fixture_routes_inputs_and_blind_spots(self, ex):
        _, out, record = ex

        def items(name):
            return json.loads((out / "extract" / f"{name}.json").read_text())["adapters"]["js"]["items"]
        js = next(a for a in record["details"]["adapters"] if a["name"] == "js")
        routes = {e["name"] for e in items("entry_points") if e["kind"] == "http-route" and e["rule"].startswith("dossier.js")}
        patterns = {b["pattern"] for b in items("blindspots")}

        assert js["tools"]["semgrep"]["status"] == "ok"
        assert {"GET /", "GET /users", "POST /users"} <= routes and not {n for n in routes if "users'" in n}
        assert {"dynamic-import", "dynamic-require", "barrel-reexport", "react-context", "hook-wiring", "string-route", "route-mount", "di-registration"} <= patterns
        assert "PORT" in {i["detail"] for i in items("io_candidates") if i["category"] == "env-var"}
