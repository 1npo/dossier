import json
import os

import pytest

import test_js_adapter_slow as base

pytestmark = pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")

ex = base.ex


def _symbols(out):
    return json.loads((out / "extract" / "symbols.json").read_text())["adapters"]["js"]["items"]


class TestScipTypescript:
    def test_defs_of_main_and_a_reference_edge_from_controller_to_service_exist(self, ex):
        _, out, record = ex

        items = _symbols(out)

        assert next(a for a in record["details"]["adapters"] if a["name"] == "js")["tools"]["scip-typescript"]["status"] == "ok"
        assert any(i["kind"] == "def" and i["path"] == "src/main.ts" for i in items)
        assert any(i["kind"] == "ref-edge" and i["path"] == "src/users/controller.ts" and i["paths"] == ["src/users/service.ts"] for i in items)

    def test_symbols_carry_no_package_name_or_version(self, ex):
        _, out, _ = ex

        defs = [i for i in _symbols(out) if i["kind"] == "def"]

        assert defs and all(i["symbol"].split(" ")[2:4] == [".", "."] for i in defs if not i["symbol"].startswith("local "))

    def test_public_means_exported_from_its_file(self, ex):
        _, out, _ = ex

        state = {i["name"]: i["public"] for i in _symbols(out) if i["kind"] == "def" and i["path"] == "src/types.ts"}

        assert state["Order"] is True and state["Local"] is False
