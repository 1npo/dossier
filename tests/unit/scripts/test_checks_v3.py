import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent / "scripts"))
import checks  # noqa: E402
import checks_v3  # noqa: E402
import render  # noqa: E402


def mod(name, path, pkg="app"):
    return {"kind": "module", "path": path, "module": name, "package": pkg, "is_package": False}


EXTRACT = {"graph": [
    mod("app.cli", "src/app/cli.py"), mod("app.store", "src/app/store.py"), mod("app.alerts", "src/app/alerts.py"),
    mod("app.util.text", "src/app/util/text.py"), mod("app.web.text", "src/app/web/text.py"),
    {"kind": "import", "path": "src/app/cli.py", "paths": ["src/app/store.py"], "from": "app.cli", "to": "app.store", "lines": [1], "via": "grimp"}],
    "symbols": [{"kind": "ref-edge", "path": "src/app/store.py", "paths": ["src/app/alerts.py"], "count": 2}]}


def reports(mermaid, card="interactions.flows"):
    return {card.split(".")[0]: {"cards": [{"card": card, "blocks": [{"type": "diagram", "mermaid": mermaid, "title": "Flow", "conf": "confirmed", "cite": ["a.py"]}]}]}}


class TestSequenceArrows:
    def test_aliases_become_node_labels(self):
        src = "sequenceDiagram\n  participant C as app.cli\n  participant S\n  C->>S: run"

        assert checks_v3.sequence_arrows(src) == [(("C", "app.cli"), ("S", "S"))]

    def test_every_arrow_form_is_read_and_replies_run_backwards(self):
        src = "sequenceDiagram\n A->B: x\n A-->B: y\n A->>B: z\n A-xB: w\n A-)B: v\n A-->>B: r"

        got = checks_v3.sequence_arrows(src)

        assert [(a[0], b[0]) for a, b in got] == [("A", "B"), ("B", "A"), ("A", "B"), ("A", "B"), ("A", "B"), ("B", "A")]


class TestFlowchartArrows:
    def test_chains_labelled_edges_and_br_labels(self):
        src = 'flowchart TD\n  subgraph one\n  A["cli<br/>entry"] -->|calls| B[store] --> C\n  end\n  C -- text --> D'

        got = checks_v3.flowchart_arrows(src)

        assert got == [(("A", "cli"), ("B", "store")), (("B", "store"), ("C", "C")), (("C", "C"), ("D", "D"))]

    def test_dotted_and_thick_edges(self):
        got = checks_v3.flowchart_arrows("graph LR\n A -.-> B\n B ==> C")

        assert [(a[0], b[0]) for a, b in got] == [("A", "B"), ("B", "C")]


class TestResolver:
    def resolver(self, rows=()):
        return checks_v3.Resolver(EXTRACT, list(rows))

    def test_exact_module(self):
        assert self.resolver().modules(("x", "app.cli")) == {"app.cli"}

    def test_unique_last_part(self):
        assert self.resolver().modules(("store", "store")) == {"app.store"}

    def test_ambiguous_last_part_is_unresolved(self):
        assert self.resolver().modules(("text", "text")) == set()

    def test_file_path(self):
        assert self.resolver().modules(("x", "src/app/alerts.py")) == {"app.alerts"}

    def test_component_name(self):
        rows = [{"name": "Web", "paths": ["src/app/web/"]}]

        assert self.resolver(rows).modules(("W", "Web")) == {"app.web.text"}


class TestResolverShortNames:
    EXTRACT = {"graph": [
        {"kind": "module", "path": "src/routes/index.ts", "module": "src/routes/index", "short": "routes", "package": None, "is_package": False, "language": "js"},
        {"kind": "module", "path": "src/store.ts", "module": "src/store", "short": "store", "package": None, "is_package": False, "language": "js"}]}

    def test_a_node_named_by_the_short_name_resolves(self):
        assert checks_v3.Resolver(self.EXTRACT, []).modules(("R", "routes")) == {"src/routes/index"}

    def test_python_modules_still_resolve_by_their_last_dotted_part(self):
        assert checks_v3.Resolver(EXTRACT, []).modules(("s", "store")) == {"app.store"}

    def test_a_csharp_node_resolves_through_the_file_stem(self):
        extract = {"graph": [{"kind": "module", "path": "src/Shop.Api/OrderService.cs", "module": "src/Shop.Api/OrderService",
                              "short": "OrderService", "language": "csharp"}]}

        assert checks_v3.Resolver(extract, []).modules(("O", "OrderService")) == {"src/Shop.Api/OrderService"}


class TestV3:
    def test_arrow_backed_by_an_import_passes(self):
        _, warnings, gaps, counts, unbacked = checks_v3.v3(reports("flowchart TD\n A[app.cli] --> B[app.store]"), EXTRACT)

        assert (warnings, gaps, unbacked) == ([], [], {})
        assert counts == {"v3": 0, "v3_checked": 1}

    def test_arrow_backed_by_a_reference_passes(self):
        _, warnings, _, _, _ = checks_v3.v3(reports("flowchart TD\n A[app.store] --> B[app.alerts]"), EXTRACT)

        assert warnings == []

    def test_unbacked_arrow_warns_gives_a_gap_item_and_a_note_key(self):
        _, warnings, gaps, counts, unbacked = checks_v3.v3(reports("flowchart TD\n A[app.alerts] --> B[app.cli]"), EXTRACT)

        assert warnings == ["V3: Key flows, diagram 1: the arrow app.alerts → app.cli has no import or call behind it."]
        assert gaps[0]["kind"] == "inference" and gaps[0]["report"] == "interactions"
        assert gaps[0]["statement"] == "In Key flows, the arrow from app.alerts to app.cli has no import or call behind it in the code."
        assert unbacked == {"interactions.flows#1": ["app.alerts → app.cli"]}
        assert counts == {"v3": 1, "v3_checked": 1}

    def test_external_participant_is_not_checked(self):
        _, warnings, _, counts, _ = checks_v3.v3(reports("sequenceDiagram\n participant U as User\n U->>app.cli: go"), EXTRACT)

        assert warnings == [] and counts["v3_checked"] == 0

    def test_other_cards_are_not_checked(self):
        _, warnings, _, _, _ = checks_v3.v3(reports("flowchart TD\n A[app.alerts] --> B[app.cli]", card="io.inputs"), EXTRACT)

        assert warnings == []

    def test_no_graph_checks_nothing_and_validate_says_so(self):
        res = checks.validate(reports("flowchart TD\n A[x] --> B[y]"), {"entry_points": []})

        assert res["warnings"] == [] and res["info"] == ["V3: no import graph was extracted, so diagram arrows were not checked."]


class TestUnbackedNote:
    def test_note_lists_the_arrows_under_the_diagram(self, make_cites):
        card = {"id": "interactions.flows", "shape": "flows"}
        blocks = [{"type": "diagram", "mermaid": "flowchart TD\n A-->B", "title": "Flow"}]

        html = render.blocks_body(card, blocks, render.Refs("interactions", make_cites({})), "t", {"interactions.flows#1": ["A → B"]})

        assert "Arrows with no import or call behind them, so treat them as inferred: A → B." in html
