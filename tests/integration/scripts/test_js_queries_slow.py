import json
import os

import pytest

import test_js_adapter_slow as base

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")

extraction = base.extraction
ex = base.ex


def _items(out, name):
    return json.loads((out / "extract" / f"{name}.json").read_text())["adapters"]["js"]["items"]


def _tests(out):
    return {i["path"]: i for i in _items(out, "tests") if i["kind"] == "test-file"}


class TestJsTests:
    def test_the_jest_file_counts_its_forms_and_imports_the_service(self, ex):
        _, out, _ = ex

        item = _tests(out)["tests/users.test.ts"]

        assert (item["framework"], item["tests"], item["skips"], item["fixtures"]) == ("jest", 1, 1, 1)
        assert item["mocks"] >= 1 and "src/users/service.ts" in item["paths"]

    def test_the_vitest_file_has_one_skip(self, ex):
        _, out, _ = ex

        item = _tests(out)["packages/web/src/App.test.tsx"]

        assert (item["framework"], item["skips"], item["tests"]) == ("vitest", 1, 1)

    def test_the_playwright_file_is_e2e(self, ex):
        _, out, _ = ex

        item = _tests(out)["e2e/smoke.spec.ts"]

        assert (item["framework"], item["test_kind"]) == ("playwright", "e2e")

    def test_the_jest_config_item_holds_the_coverage_threshold(self, ex):
        _, out, _ = ex

        config = next(i for i in _items(out, "tests") if i["kind"] == "config" and i["tool"] == "jest")

        assert "coverage_threshold" in config["settings"]


class TestJsSyntax:
    def test_module_state_finds_current_and_cache_but_not_the_constant(self, ex):
        _, out, _ = ex

        names = {i["name"] for i in _items(out, "io_candidates") if i["rule"] == "dossier.js.state.module-mutable"}

        assert {"current", "cache"} <= names and "NAMES" not in names

    def test_complexity_is_recorded_on_modules(self, ex):
        _, out, _ = ex

        service = next(i for i in _items(out, "graph") if i["kind"] == "module" and i["path"] == "src/users/service.ts")

        assert service["complexity"] > 0
