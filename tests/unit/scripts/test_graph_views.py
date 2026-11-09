import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent / "scripts"))

import graph_views  # noqa: E402


def flat(n, prefix="a"):
    return {f"{prefix}{i:02d}": None for i in range(n)}


def with_children(areas, per_area, prefix="c"):
    levels = {f"area{a:02d}": None for a in range(areas)}
    for a in range(areas):
        for c in range(per_area):
            levels[f"{prefix}{a:02d}_{c:02d}"] = f"area{a:02d}"
    return levels


def by_title(found):
    return {v["title"]: v for v in found}


def reachable(found):
    seen = set()
    for v in found:
        seen |= {n["label"] for n in v["nodes"]}
    return seen


class TestViews:
    def test_five_areas_give_one_root_view_of_five_nodes(self):
        levels = flat(5)

        found = graph_views.views(levels, {}, "Areas")

        assert len(found) == 1
        assert found[0]["parent"] is None and found[0]["title"] == "Areas"
        assert len(found[0]["nodes"]) == 5

    def test_thirty_areas_fold_into_three_groups_with_views_of_ten(self):
        levels = flat(30)

        found = graph_views.views(levels, {}, "Areas")

        root = found[0]
        assert [n["kind"] for n in root["nodes"]] == ["group"] * 3
        assert [n["label"] for n in root["nodes"]][0] == "a00 … a09 (10)"
        assert len(found) == 4
        assert [len(v["nodes"]) for v in found[1:]] == [10, 10, 10]
        assert all(n["view"] for n in root["nodes"])

    def test_an_area_with_twenty_five_components_gives_groups_of_ten_ten_and_five(self):
        levels = {"big": None, **{f"c{i:02d}": "big" for i in range(25)}}

        found = graph_views.views(levels, {}, "Areas")

        area = by_title(found)["big"]
        assert [n["label"] for n in area["nodes"]] == ["c00 … c09 (10)", "c10 … c19 (10)", "c20 … c24 (5)"]
        assert [len(by_title(found)[n["label"]]["nodes"]) for n in area["nodes"]] == [10, 10, 5]

    def test_a_group_of_more_than_twelve_groups_is_folded_again(self):
        levels = flat(150)

        found = graph_views.views(levels, {}, "Areas")

        assert len(found[0]["nodes"]) <= graph_views.MAX_NODES
        assert reachable(found) >= set(levels)

    def test_neighbours_past_twelve_fold_into_one_other_node(self):
        levels = {"home": None, "hc0": "home", "hc1": "home", **{f"o{i:02d}": None for i in range(20)}}
        levels.update({f"oc{i:02d}": f"o{i:02d}" for i in range(20)})
        edges = {("hc0", f"oc{i:02d}"): 1 for i in range(20)}

        found = graph_views.views(levels, edges, "Areas")

        home = by_title(found)["home"]
        others = [n for n in home["nodes"] if n["kind"] == "other"]
        assert [n["label"] for n in others] == ["20 other areas"]
        assert len(home["nodes"]) == 3

    def test_a_few_neighbours_stay_separate_nodes(self):
        levels = {"home": None, "hc0": "home", "o1": None, "oc1": "o1", "o2": None, "oc2": "o2"}
        edges = {("hc0", "oc1"): 2, ("oc2", "hc0"): 3}

        found = graph_views.views(levels, edges, "Areas")

        home = by_title(found)["home"]
        assert sorted(n["label"] for n in home["nodes"]) == ["hc0", "o1", "o2"]
        assert sorted(e["weight"] for e in home["edges"]) == [2, 3]

    def test_every_leaf_is_a_node_of_at_least_one_view(self):
        levels = with_children(6, 14)
        edges = {(f"c00_{i:02d}", f"c01_{i:02d}"): 1 for i in range(14)}

        found = graph_views.views(levels, edges, "Areas")

        leaves = {n for n in levels if levels[n] is not None}
        assert reachable(found) >= leaves

    def test_every_view_has_at_most_twelve_nodes_and_thirty_edges(self):
        levels = with_children(40, 25)
        edges = {(f"c{a:02d}_{c:02d}", f"c{(a * 7 + c) % 40:02d}_{(c * 3) % 25:02d}"): 1 + (a + c) % 4 for a in range(40) for c in range(25)}

        found = graph_views.views(levels, edges, "Areas")

        assert all(len(v["nodes"]) <= graph_views.MAX_NODES for v in found)
        assert all(len(v["edges"]) <= graph_views.MAX_EDGES for v in found)

    def test_forty_seven_weighted_edges_keep_the_smallest_threshold_that_fits(self):
        levels = flat(12)
        pairs = [(f"a{i:02d}", f"a{j:02d}") for i in range(12) for j in range(12) if i != j]
        edges = {pair: 1 + n % 3 for n, pair in enumerate(pairs[:47])}
        weights = sorted(edges.values())

        view = graph_views.views(levels, edges, "Areas")[0]

        w = view["hidden"]["w"]
        assert sum(1 for x in weights if x >= w) <= 30 < sum(1 for x in weights if x >= w - 1)
        assert view["hidden"] == {"w": w, "shown": len(view["edges"]), "total": 47}
        assert all(e["weight"] >= w for e in view["edges"])

    def test_a_tie_at_the_boundary_drops_the_whole_tie(self):
        levels = {**flat(6, "p"), **{f"q{i:02d}": None for i in range(6)}}
        edges = {(f"p{i:02d}", f"q{j:02d}"): 5 if (i + j) % 2 else 1 for i in range(6) for j in range(6) if i != j or True}
        heavy = sum(1 for x in edges.values() if x == 5)
        assert heavy <= 30 < len(edges)

        view = graph_views.views(levels, edges, "Areas")[0]

        assert len(view["edges"]) == heavy
        assert view["hidden"]["w"] == 2

    def test_a_view_that_fits_has_no_hidden_record(self):
        levels = flat(3)

        view = graph_views.views(levels, {("a00", "a01"): 1}, "Areas")[0]

        assert view["hidden"] is None
        assert len(view["edges"]) == 1

    def test_weights_add_up_between_aggregated_nodes(self):
        levels = {"x": None, "x1": "x", "x2": "x", "y": None, "y1": "y"}
        edges = {("x1", "y1"): 2, ("x2", "y1"): 3}

        view = graph_views.views(levels, edges, "Areas")[0]

        label = {n["id"]: n["label"] for n in view["nodes"]}
        assert [(label[e["from"]], label[e["to"]], e["weight"]) for e in view["edges"]] == [("x", "y", 5)]

    def test_a_three_level_hierarchy_gives_a_view_for_each_component(self):
        levels = {"app": None, "web": "app", "m1": "web", "m2": "web", "db": "app", "m3": "db"}
        edges = {("m1", "m3"): 1}

        found = graph_views.views(levels, edges, "Areas", ("area", "component", "module"))

        titles = [v["title"] for v in found]
        assert titles == ["Areas", "app", "db", "web"]
        assert by_title(found)["web"]["edges"][0]["weight"] == 1
        assert [n["label"] for n in by_title(found)["web"]["nodes"]] == ["m1", "m2", "db"]

    def test_view_ids_and_parents_are_consistent(self):
        found = graph_views.views(with_children(30, 3), {}, "Areas")

        ids = {v["id"] for v in found}
        assert len(ids) == len(found)
        assert all(v["parent"] in ids | {None} for v in found)
        assert all(c in ids for v in found for c in v["children"])

    def test_node_ids_are_unique_in_a_view(self):
        levels = {"a-b": None, "a b": None, "a.b": None}

        view = graph_views.views(levels, {}, "Areas")[0]

        assert len({n["id"] for n in view["nodes"]}) == 3

    def test_no_nodes_give_no_views(self):
        assert graph_views.views({}, {}, "Areas") == []

    def test_a_self_import_inside_one_node_draws_no_edge(self):
        levels = {"x": None, "x1": "x", "x2": "x"}

        view = graph_views.views(levels, {("x1", "x2"): 4}, "Areas")[0]

        assert view["edges"] == []


class TestViewLabels:
    def test_two_nodes_may_share_a_label_through_the_labels_map(self):
        levels = {"a:api": None, "c:api": "a:api"}

        found = graph_views.views(levels, {}, "Areas", labels={"a:api": "api", "c:api": "api"})

        assert [n["label"] for n in found[1]["nodes"]] == ["api"]
        assert found[1]["title"] == "api"


class TestMermaid:
    def test_source_is_a_flowchart_with_one_line_per_node_and_edge(self):
        levels = {"x": None, "x1": "x", "y": None, "y1": "y", "z": None, "z1": "z"}
        edges = {("x1", "y1"): 2, ("y1", "z1"): 1}

        view = graph_views.views(levels, edges, "Areas")[0]
        src = graph_views.mermaid(view)

        lines = src.splitlines()
        assert lines[0] == "flowchart LR"
        assert sum(1 for line in lines if "-->" in line) == 2
        assert sum(1 for line in lines[1:] if "-->" not in line) == 3
        assert any("-->|2|" in line for line in lines)
        assert view["src"] == src

    def test_quotes_in_a_label_are_escaped(self):
        view = graph_views.views({'say "hi"': None}, {}, "Areas")[0]

        assert '"' not in graph_views.mermaid(view).splitlines()[1].split('["', 1)[1][:-2]
