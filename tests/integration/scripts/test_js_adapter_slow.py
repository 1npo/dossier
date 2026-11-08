import json
import os
import subprocess
from types import SimpleNamespace

import pytest

import buildlog
import stages
import workarea
from conftest import build_js_repo, key_line, line_of

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")

LANGS = ["TypeScript", "JavaScript", "JSON"]
UNTRUSTED = {"trusted": False, "why": "the ref is not a tag or the default branch", "default_branch": None}


def _extract(repo, out, area, checkout, trusted, tag):
    build = buildlog.start(out, repo="jsrepo", sha=repo.sha, ref="main", version=tag, options={})
    return stages.stage_extract(build, repo.path, repo.sha, area, out, LANGS, trusted, stages.Options(no_restore=True), {},
                                stages.tree_at(repo.path, repo.sha), checkout)


def _build(base_dir, trusted):
    patch = pytest.MonkeyPatch()
    patch.setenv("DOSSIER_HOME", str(base_dir / "home"))
    patch.setenv("DOSSIER_CONFIG", str(base_dir / "cfg.json"))
    patch.setenv("DOSSIER_CACHE", str(base_dir / "cache"))
    repo = build_js_repo(base_dir)
    out = base_dir / "home" / "jsrepo"
    area = workarea.area_for("jsrepo", repo.path, repo.sha, base_dir / "cache")
    checkout = workarea.ensure_checkout(area, repo.path, repo.sha)["path"]
    record = _extract(repo, out, area, checkout, trusted(repo) if callable(trusted) else trusted, "test")
    return patch, SimpleNamespace(repo=repo, out=out, record=record, area=area, checkout=checkout, trusted=trusted)


@pytest.fixture(scope="module")
def extraction(tmp_path_factory):
    """One extraction of the JavaScript fixture repository with every tool."""
    patch, got = _build(tmp_path_factory.mktemp("jsadapter"), lambda repo: workarea.trusted(repo.path, repo.sha))
    try:
        yield got
    finally:
        patch.undo()


@pytest.fixture(scope="module")
def ex(extraction):
    return extraction.repo, extraction.out, extraction.record


@pytest.fixture(scope="module")
def untrusted(tmp_path_factory):
    patch, got = _build(tmp_path_factory.mktemp("jsuntrusted"), UNTRUSTED)
    try:
        yield got
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


def section(out, name, adapter="js"):
    return json.loads((out / "extract" / f"{name}.json").read_text())["adapters"][adapter]["items"]


class TestFixtureOfRecord:
    """Every extract/*.json output of the JavaScript adapter on the fixture repository, against the markers in its files."""

    def test_entry_points_are_exactly_the_expected_list_with_marker_lines(self, extraction):
        repo, out = extraction.repo, extraction.out
        root = repo.path

        got = {(e["kind"], e["name"], e["path"]) for e in section(out, "entry_points")}

        expected = {("package-bin", "shopjs", "package.json"), ("package-main", "dist/main.js", "package.json"),
                    ("package-script", "shopjs start", "package.json"), ("package-script", "shopjs test", "package.json"),
                    ("package-script", "prisma seed", "package.json"), ("package-main", "./dist/index.d.ts", "packages/lib/package.json"),
                    ("http-route", "/items/[id]", "packages/site/app/(shop)/items/[id]/page.tsx"),
                    ("http-route", "API /api/ping", "packages/site/app/api/ping/route.ts"), ("http-route", "/", "packages/site/app/page.tsx"),
                    ("http-route", "/about", "packages/site/pages/about.tsx"),
                    ("ui-route", "/", "packages/web/src/router.tsx"), ("ui-route", "/cart", "packages/web/src/router.tsx"),
                    ("ui-route", "prefix + '/x'", "packages/web/src/router.tsx"), ("ui-route", "/home", "packages/web/src/router.tsx"),
                    ("nx-target", "shopjs:serve", "project.json"), ("nx-target", "shopjs:build", "project.json"),
                    ("cli-command", "sync", "src/cli.ts"), ("scheduled-job", "0 * * * *", "src/jobs.ts"), ("queue-consumer", "mail", "src/jobs.ts"),
                    ("http-route", "GET /", "src/main.ts"), ("server-listen", "listen", "src/main.ts"),
                    ("http-route", "GET /users", "src/users/controller.ts"), ("http-route", "POST /users", "src/users/controller.ts")}
        assert got == expected
        lines = {(e["kind"], e["name"]): e["line"] for e in section(out, "entry_points")}
        assert lines[("http-route", "GET /")] == line_of(root, "src/main.ts", "ep-root")
        assert lines[("server-listen", "listen")] == line_of(root, "src/main.ts", "ep-listen")
        assert lines[("http-route", "GET /users")] == line_of(root, "src/users/controller.ts", "ep-get")
        assert lines[("http-route", "POST /users")] == line_of(root, "src/users/controller.ts", "ep-post")
        assert lines[("cli-command", "sync")] == line_of(root, "src/cli.ts", "ep-cli")
        assert lines[("scheduled-job", "0 * * * *")] == line_of(root, "src/jobs.ts", "ep-cron")
        assert lines[("queue-consumer", "mail")] == line_of(root, "src/jobs.ts", "ep-queue")
        assert lines[("ui-route", "/")] == line_of(root, "packages/web/src/router.tsx", "ui-literal")
        assert lines[("package-bin", "shopjs")] == key_line(root, "package.json", "bin") + 1
        controller = {e["line"] for e in section(out, "entry_points") if e["path"] == "src/users/controller.ts"}
        assert line_of(root, "src/users/controller.ts", "not-route") not in controller
        assert line_of(root, "src/users/controller.ts", "bs-route") not in controller

    def test_graph_has_the_run_time_cycle_the_broken_rule_the_alias_and_the_source_root(self, extraction):
        graph = section(extraction.out, "graph")

        assert [c["modules"] for c in graph if c["kind"] == "cycle"] == [["src/a", "src/b"]]
        contract = next(c for c in graph if c["kind"] == "contract")
        assert (contract["status"], contract["contract"]) == ("broken", "no-service-to-main")
        assert (contract["violations"][0]["path"], contract["violations"][0]["to"]) == ("src/users/service.ts", "src/main")
        assert any(i["kind"] == "import" and (i["from"], i["to"]) == ("src/unused", "src/a") for i in graph)
        assert not [m for m in graph if m["kind"] == "module" and (m["path"].endswith((".d.ts", ".test.ts", ".test.tsx")) or m["path"].startswith("tests/"))]
        assert [(r["path"], r["root"]) for r in graph if r["kind"] == "source-root"] == [("package.json", "src")]
        assert all(m["language"] == "js" for m in graph if m["kind"] == "module")

    def test_symbols_have_defs_edges_and_the_public_flag(self, extraction):
        symbols = section(extraction.out, "symbols")

        assert any(s["kind"] == "def" and s["path"] == "src/main.ts" for s in symbols)
        assert any(s["kind"] == "ref-edge" and s["path"] == "src/users/controller.ts" and s["paths"] == ["src/users/service.ts"] for s in symbols)
        state = {s["name"]: s["public"] for s in symbols if s["kind"] == "def" and s["path"] == "src/types.ts"}
        assert state["Order"] is True and state["Local"] is False

    def test_io_candidates_carry_the_marker_lines_with_their_categories(self, extraction):
        root, found = extraction.repo.path, section(extraction.out, "io_candidates")
        have = {(i["path"], i["line"], i["category"]) for i in found}
        expected = [("src/main.ts", "io-env", "env-var"), ("src/main.ts", "io-log", "log"), ("src/users/controller.ts", "io-error", "error-response"),
                    ("src/users/service.ts", "io-db", "db-access"), ("src/users/service.ts", "io-outbound", "outbound-call"),
                    ("src/db.ts", "io-db-connect", "db-connect"), ("src/cli.ts", "io-exit", "exit-code"),
                    ("src/users/service.ts", "fail-tx", "transaction"), ("src/users/service.ts", "fail-catch", "catch-all"),
                    ("src/state.ts", "state-let", "global-state"), ("src/state.ts", "state-map", "global-state"),
                    ("prisma/schema.prisma", "prisma-env", "env-var")]

        for path, marker, category in expected:
            assert (path, line_of(root, path, marker), category) in have, marker
        assert "DATABASE_URL" in {i["detail"] for i in found if i["category"] == "env-var"}
        assert not [i for i in found if i.get("name") == "NAMES"]

    def test_models_are_the_entities_and_nothing_else(self, extraction):
        got = {(m["name"], m["kind"]) for m in section(extraction.out, "models")}

        assert got == {("User", "prisma"), ("Post", "prisma"), ("Role", "prisma-enum"), ("Product", "typeorm"), ("Status", "ts-enum"),
                       ("Order", "ts-interface"), ("Item", "ts-type")}

    def test_tests_hold_the_three_files_the_configs_and_the_ci_command(self, extraction):
        tests = section(extraction.out, "tests")
        files = {t["path"]: (t["framework"], t["test_kind"]) for t in tests if t["kind"] == "test-file"}

        assert files == {"tests/users.test.ts": ("jest", "unit"), "packages/web/src/App.test.tsx": ("vitest", "unit"), "e2e/smoke.spec.ts": ("playwright", "e2e")}
        assert {t["tool"] for t in tests if t["kind"] == "config"} == {"jest", "vitest"}
        assert [t["command"] for t in section(extraction.out, "tests", "repo") if t["kind"] == "ci-command"] == ["npx jest"]
        assert next(t for t in tests if t.get("path") == "tests/users.test.ts")["paths"] == ["src/users/service.ts"]

    def test_dead_code_holds_the_unreferenced_file_and_an_unused_export(self, extraction):
        dead = section(extraction.out, "dead")

        assert any(d["type"] == "unused file" and d["path"] == "src/unused.ts" for d in dead)
        assert any(d["type"] == "unused export" and d["name"] == "hidden" for d in dead)
        assert all(d["confidence"] is None and d["id"].startswith("dd-") for d in dead)

    def test_blind_spots_are_the_markers_with_their_patterns(self, extraction):
        root, found = extraction.repo.path, section(extraction.out, "blindspots")
        have = {(b["path"], b["line"], b["pattern"]) for b in found}
        expected = [("src/plugins.ts", "bs-import", "dynamic-import"), ("src/plugins.ts", "bs-require", "dynamic-require"),
                    ("src/plugins.ts", "bs-di", "di-registration"), ("src/routes.ts", "bs-mount", "route-mount"),
                    ("src/users/controller.ts", "bs-route", "string-route"), ("src/barrel/index.ts", "bs-barrel", "barrel-reexport"),
                    ("packages/web/src/context.tsx", "bs-context", "react-context"), ("packages/web/src/context.tsx", "bs-hook", "hook-wiring")]

        for path, marker, pattern in expected:
            assert (path, line_of(root, path, marker), pattern) in have, marker
        assert "feature-flag" in {b["pattern"] for b in section(extraction.out, "blindspots", "repo")}

    def test_every_candidate_has_an_id_and_a_group(self, extraction):
        for name in ("entry_points", "io_candidates", "models", "blindspots"):
            assert all(i["id"] and i["group"] for i in section(extraction.out, name)), name

    def test_every_tool_is_ok_and_the_checkout_has_no_tracked_change(self, extraction):
        js = next(a for a in extraction.record["details"]["adapters"] if a["name"] == "js")
        status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=extraction.checkout, capture_output=True, text=True)

        assert {t: v["status"] for t, v in js["tools"].items()} == {t: "ok" for t in js["tools"]}
        assert status.stdout == ""

    def test_a_second_run_reuses_every_section(self, extraction):
        second = _extract(extraction.repo, extraction.out, extraction.area, extraction.checkout, workarea.trusted(extraction.repo.path, extraction.repo.sha), "again")

        assert second["status"] == "reused" or {a["status"] for a in second["details"]["adapters"]} == {"reused"}


class TestUntrustedRef:
    def test_the_four_node_tools_are_skipped_and_the_pattern_routes_remain(self, untrusted):
        js = next(a for a in untrusted.record["details"]["adapters"] if a["name"] == "js")

        for tool in ("dependency-cruiser", "knip", "scip-typescript", "typescript"):
            assert js["tools"][tool]["status"] == "skipped" and "not trusted" in js["tools"][tool]["reason"]
        assert js["tools"]["semgrep"]["status"] == "ok" and js["tools"]["tree-sitter-language-pack"]["status"] == "ok"
        names = {e["name"] for e in section(untrusted.out, "entry_points") if e["kind"] == "http-route"}
        assert {"GET /", "GET /users", "POST /users"} <= names
