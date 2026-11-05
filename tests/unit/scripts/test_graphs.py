import random

import graphs


class TestCycles:
    def test_a_three_cycle_and_a_two_cycle_with_a_tail_give_exactly_two_cycles(self):
        edges = [("a", "b"), ("b", "c"), ("c", "a"), ("x", "y"), ("y", "x"), ("c", "x"), ("y", "tail")]

        assert graphs.cycles(edges) == [["a", "b", "c"], ["x", "y"]]

    def test_a_self_import_is_ignored(self):
        assert graphs.cycles([("a", "a"), ("a", "b")]) == []

    def test_no_edges_give_no_cycles(self):
        assert graphs.cycles([]) == []

    def test_a_long_chain_does_not_exhaust_the_stack(self):
        edges = [(str(i), str(i + 1)) for i in range(5000)] + [("5000", "0")]

        got = graphs.cycles(edges)

        assert len(got) == 1 and len(got[0]) == 5001


class TestPagerank:
    def test_ranks_sum_to_one(self):
        got = graphs.pagerank(["a", "b", "c"], [("a", "c"), ("b", "c")])

        assert abs(sum(got.values()) - 1) < 1e-9

    def test_a_hub_ranks_above_its_leaves(self):
        got = graphs.pagerank([], [("a", "hub"), ("b", "hub"), ("c", "hub")])

        assert got["hub"] > max(got["a"], got["b"], got["c"])

    def test_empty_graph_gives_empty_ranks(self):
        assert graphs.pagerank([], []) == {}


class TestCommunities:
    def test_two_disconnected_triangles_are_two_labels(self):
        edges = [("a", "b"), ("b", "c"), ("c", "a"), ("x", "y"), ("y", "z"), ("z", "x")]

        got = graphs.communities([], edges)

        assert len(set(got.values())) == 2 and got["a"] == got["b"] == got["c"] and got["x"] == got["y"] == got["z"]

    def test_isolated_node_keeps_its_own_label(self):
        assert graphs.communities(["solo"], [])["solo"] == "solo"

    def test_result_is_the_same_with_shuffled_input(self):
        edges = [("a", "b"), ("b", "c"), ("c", "a"), ("c", "d"), ("d", "e"), ("e", "f"), ("f", "d")]
        shuffled = edges[:]
        random.Random(1).shuffle(shuffled)

        assert graphs.communities([], edges) == graphs.communities([], shuffled)


class TestAggregate:
    def test_edges_inside_a_group_are_dropped_and_the_rest_summed(self):
        group = {"a": "X", "b": "X", "c": "Y", "d": "Y"}

        got = graphs.aggregate([("a", "b"), ("a", "c"), ("b", "d"), ("c", "a")], group)

        assert got == {("X", "Y"): 2, ("Y", "X"): 1}

    def test_edge_with_an_ungrouped_end_is_dropped(self):
        assert graphs.aggregate([("a", "zzz")], {"a": "X"}) == {}


class TestReverseClosure:
    def test_chain_gives_every_upstream_file(self):
        got = graphs.reverse_closure(["a", "b", "c"], [("a", "b"), ("b", "c")])

        assert got == {"a": set(), "b": {"a"}, "c": {"a", "b"}}

    def test_diamond_counts_each_dependent_once(self):
        got = graphs.reverse_closure(list("abcd"), [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")])

        assert got["d"] == {"a", "b", "c"}

    def test_a_file_is_never_its_own_dependent_even_in_a_cycle(self):
        got = graphs.reverse_closure(["a", "b"], [("a", "b"), ("b", "a")])

        assert got == {"a": {"b"}, "b": {"a"}}

    def test_edges_to_unknown_nodes_are_ignored(self):
        assert graphs.reverse_closure(["a"], [("a", "z")]) == {"a": set()}
