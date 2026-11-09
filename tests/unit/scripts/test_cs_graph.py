import cs_graph


def t(name, ns, partial=False):
    return {"name": name, "namespace": ns, "partial": partial}


def f(namespaces=(), types=(), usings=(), idents=(), qualified=()):
    return {"namespaces": [{"name": n} for n in namespaces], "types": list(types), "qualified": list(qualified),
            "usings": [{"name": u, "global": False, "static": False, "alias": None} for u in usings],
            "idents": {i: [3] for i in idents}}


def proj(path, files, refs=()):
    return {"path": path, "dir": path.rsplit("/", 1)[0], "name": path.split("/")[-1][:-7], "files": list(files), "references": list(refs)}


def world(*projects):
    return {"projects": list(projects)}


P = world(proj("A/A.csproj", ["A/x.cs", "A/y.cs", "A/z.cs"]), proj("B/B.csproj", ["B/b.cs"], ["A/A.csproj"]), proj("C/C.csproj", ["C/c.cs"]))


def uses(decls, projects=P, **kw):
    return cs_graph.type_uses(decls, projects, **kw)


class TestTypeUses:
    def test_a_use_through_using_links_the_files(self):
        d = {"A/x.cs": f(["A.One"], [t("X", "A.One")]), "A/y.cs": f(["A.Two"], [t("Y", "A.Two")], usings=["A.One"], idents=["X"])}

        imports, _, amb = uses(d)

        assert [(i["path"], i["paths"], i["names"], i["via"], i["lines"]) for i in imports] == [("A/y.cs", ["A/x.cs"], ["X"], "type-use", [3])]
        assert amb == 0

    def test_a_use_in_the_same_namespace_links(self):
        d = {"A/x.cs": f(["A"], [t("X", "A")]), "A/y.cs": f(["A"], [t("Y", "A")], idents=["X"])}

        assert [(i["path"], i["paths"][0]) for i in uses(d)[0]] == [("A/y.cs", "A/x.cs")]

    def test_a_use_from_a_parent_namespace_links(self):
        d = {"A/x.cs": f(["A"], [t("X", "A")]), "A/y.cs": f(["A.Deep.Er"], [t("Y", "A.Deep.Er")], idents=["X"])}

        assert len(uses(d)[0]) == 1

    def test_a_name_not_visible_is_not_linked(self):
        d = {"A/x.cs": f(["A.One"], [t("X", "A.One")]), "A/y.cs": f(["Other"], [t("Y", "Other")], idents=["X"])}

        assert uses(d)[0] == []

    def test_a_use_across_a_missing_project_reference_does_not_link(self):
        d = {"C/c.cs": f(["C"], [t("K", "C")], usings=["A"], idents=["X"]), "A/x.cs": f(["A"], [t("X", "A")])}

        assert uses(d)[0] == []

    def test_a_use_across_a_project_reference_links(self):
        d = {"B/b.cs": f(["B"], [t("K", "B")], usings=["A"], idents=["X"]), "A/x.cs": f(["A"], [t("X", "A")])}

        assert [(i["path"], i["paths"][0]) for i in uses(d)[0]] == [("B/b.cs", "A/x.cs")]

    def test_two_different_types_with_one_name_give_no_edge_and_count_one(self):
        d = {"A/x.cs": f(["A.One"], [t("Item", "A.One")]), "A/y.cs": f(["A.Two"], [t("Item", "A.Two")]),
             "A/z.cs": f(["A.Z"], [t("Z", "A.Z")], usings=["A.One", "A.Two"], idents=["Item"])}

        imports, _, amb = uses(d)

        assert imports == [] and amb == 1

    def test_a_partial_type_links_to_both_parts(self):
        d = {"A/x.cs": f(["A"], [t("Totals", "A", True)]), "A/y.cs": f(["A"], [t("Totals", "A", True)]), "A/z.cs": f(["A"], [t("Z", "A")], idents=["Totals"])}

        assert sorted(i["paths"][0] for i in uses(d)[0]) == ["A/x.cs", "A/y.cs"]

    def test_a_type_in_the_files_own_namespace_beats_a_using(self):
        d = {"A/x.cs": f(["A.One"], [t("Item", "A.One")]), "A/y.cs": f(["A.Two"], [t("Item", "A.Two")]),
             "A/z.cs": f(["A.One"], [t("Z", "A.One")], usings=["A.Two"], idents=["Item"])}

        assert [(i["path"], i["paths"][0]) for i in uses(d)[0]] == [("A/z.cs", "A/x.cs")]

    def test_a_name_written_with_its_namespace_links(self):
        d = {"A/x.cs": f(["A.One"], [t("X", "A.One")]), "A/y.cs": f(["Other"], [t("Y", "Other")], idents=["X"], qualified=["A.One.X"])}

        assert len(uses(d)[0]) == 1

    def test_a_file_that_declares_the_name_itself_is_not_linked_for_it(self):
        d = {"A/x.cs": f(["A"], [t("X", "A")]), "A/y.cs": f(["A"], [t("X", "A")], idents=["X"])}

        assert uses(d)[0] == []

    def test_a_generated_file_has_no_outgoing_edges_but_keeps_incoming_ones(self):
        d = {"A/x.cs": f(["A"], [t("X", "A")], idents=["Y"]), "A/y.cs": f(["A"], [t("Y", "A")], idents=["X"])}

        imports, _, _ = uses(d, generated={"A/x.cs"})

        assert [(i["path"], i["paths"][0]) for i in imports] == [("A/y.cs", "A/x.cs")]

    def test_edges_from_test_files_become_test_edges(self):
        d = {"A/x.cs": f(["A"], [t("X", "A")]), "A/y.cs": f(["A"], [t("YTests", "A")], idents=["X"])}

        imports, test_edges, _ = uses(d, test_files={"A/y.cs"})

        assert imports == [] and test_edges == [("A/y.cs", "A/x.cs")]

    def test_test_files_are_not_targets(self):
        d = {"A/x.cs": f(["A"], [t("X", "A")], idents=["Helper"]), "A/y.cs": f(["A"], [t("Helper", "A")])}

        assert uses(d, test_files={"A/y.cs"})[0] == []


class TestNamespaceCycles:
    def _imp(self, a, b):
        return {"kind": "import", "path": a, "paths": [b]}

    def test_a_cycle_between_two_namespaces_is_one_item(self):
        d = {"A/x.cs": f(["A.One"]), "A/y.cs": f(["A.Two"])}

        got = cs_graph.namespace_cycles([self._imp("A/x.cs", "A/y.cs"), self._imp("A/y.cs", "A/x.cs")], d, P)

        assert [(c["modules"], c["level"], c["project"], c["paths"]) for c in got] == [(["A.One", "A.Two"], "namespace", "A/A.csproj", ["A/x.cs", "A/y.cs"])]

    def test_two_files_that_use_each_other_in_one_namespace_give_none(self):
        d = {"A/x.cs": f(["A.One"]), "A/y.cs": f(["A.One"])}

        assert cs_graph.namespace_cycles([self._imp("A/x.cs", "A/y.cs"), self._imp("A/y.cs", "A/x.cs")], d, P) == []

    def test_one_way_use_between_namespaces_gives_none(self):
        d = {"A/x.cs": f(["A.One"]), "A/y.cs": f(["A.Two"])}

        assert cs_graph.namespace_cycles([self._imp("A/x.cs", "A/y.cs")], d, P) == []


class TestModuleItems:
    def test_a_module_item_has_the_d8_fields(self):
        d = {"A/x.cs": f(["A"], [t("X", "A")])}

        item = cs_graph.module_items(P, d, {"A/x.cs": 4}, set())[0]

        assert item == {"kind": "module", "path": "A/x.cs", "module": "A/x", "short": "x", "namespaces": ["A"], "project": "A/A.csproj",
                        "language": "csharp", "generated": False, "complexity": 4}

    def test_a_generated_file_has_complexity_zero(self):
        d = {"A/x.cs": f(["A"])}

        item = cs_graph.module_items(P, d, {"A/x.cs": 4}, {"A/x.cs"})[0]

        assert (item["generated"], item["complexity"]) == (True, 0)

    def test_test_files_are_not_modules(self):
        d = {"A/x.cs": f(["A"]), "A/y.cs": f(["A"])}

        assert [i["path"] for i in cs_graph.module_items(P, d, {}, set(), {"A/y.cs"})] == ["A/x.cs"]
