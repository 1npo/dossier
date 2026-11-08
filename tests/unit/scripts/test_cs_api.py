import cs_api


def member(name, kind="method", mods=("public",), line=5, params=(), attrs=()):
    return {"name": name, "kind": kind, "modifiers": list(mods), "line": line, "end_line": line, "attributes": [{"name": a, "args": g, "line": line} for a, g in attrs],
            "type": "int", "static": "static" in mods, "params": [{"name": p, "type": "int", "this": this, "attrs": []} for p, this in params]}


def typ(name, members=(), mods=("public",), kind="class", outer=None, partial=False, line=3, attrs=(), ns="Shop.Core", params=()):
    return {"name": name, "kind": kind, "modifiers": list(mods), "line": line, "end_line": line + 10, "attributes": [{"name": a, "args": g, "line": line} for a, g in attrs],
            "bases": [], "partial": partial, "outer": outer, "namespace": ns, "params": [{"name": p, "type": "int", "this": False, "attrs": []} for p in params],
            "members": list(members)}


def file(*types):
    return {"namespaces": [], "usings": [], "types": list(types), "top_level": False, "idents": {}, "qualified": [], "assembly_attributes": []}


def project(name="Shop.Core", files=("a.cs",), packable=True, test=False, friends=(), package_id=None):
    return {"path": f"src/{name}/{name}.csproj", "name": name, "packable": packable, "test": test, "package_id": package_id or (name if packable else None),
            "assembly": name, "friends": list(friends), "files": list(files)}


CORE = {
    "a.cs": file(typ("Order"), typ("Secret", mods=("internal",)), typ("Outer", [member("P", mods=("protected",)), member("Q", mods=("private",))]),
                 typ("Inner", outer="Outer", line=5), typ("Hidden", attrs=[("EditorBrowsable", "EditorBrowsableState.Never")], line=20)),
    "b.cs": file(typ("IClock", [member("Now", kind="property", mods=())], kind="interface"),
                 typ("Money", [member("Round", mods=("public", "static"), params=[("v", False)]),
                               member("Round", mods=("public", "static"), line=7, params=[("v", False), ("n", False)]),
                               member("Shout", mods=("public", "static"), line=9, params=[("s", True)])], mods=("public", "static"))),
    "c.cs": file(typ("Totals", [], partial=True)),
    "d.cs": file(typ("Totals", [member("Total")], mods=(), partial=True)),
    "poly.cs": file(typ("CallerArgumentExpressionAttribute", mods=("internal", "sealed"))),
}


def rows(projects, decls, generated=()):
    symbols, notes, friends = cs_api.items(projects, decls, set(generated))
    return {s["name"]: s for s in symbols}, notes, friends


class TestIsPublic:
    def test_public_type_is_public(self):
        assert cs_api.is_public(typ("A"), [], [])

    def test_no_modifier_on_a_type_is_internal(self):
        assert not cs_api.is_public(typ("A", mods=()), [], [])

    def test_internal_type_is_not_public(self):
        assert not cs_api.is_public(typ("A", mods=("internal",)), [], [])

    def test_file_type_is_not_public(self):
        assert not cs_api.is_public(typ("A", mods=("file",)), [], [])

    def test_protected_internal_member_is_public(self):
        assert cs_api.is_public(member("M", mods=("protected", "internal")), [typ("A")], [])

    def test_private_protected_member_is_not_public(self):
        assert not cs_api.is_public(member("M", mods=("private", "protected")), [typ("A")], [])

    def test_member_with_no_modifier_is_private(self):
        assert not cs_api.is_public(member("M", mods=()), [typ("A")], [])

    def test_interface_member_with_no_modifier_takes_the_interface(self):
        assert cs_api.is_public(member("M", mods=()), [typ("I", kind="interface")], [])
        assert not cs_api.is_public(member("M", mods=()), [typ("I", kind="interface", mods=("internal",))], [])

    def test_enum_member_takes_the_enum(self):
        assert cs_api.is_public(member("New", kind="enum-member", mods=()), [typ("E", kind="enum")], [])

    def test_public_member_of_an_internal_type_is_not_public(self):
        assert not cs_api.is_public(member("M"), [typ("A", mods=("internal",))], [])

    def test_nested_type_needs_every_outer_to_be_public(self):
        inner = typ("Inner", outer="Outer")

        assert cs_api.is_public(inner, [typ("Outer")], [])
        assert not cs_api.is_public(inner, [typ("Outer", mods=("internal",))], [])

    def test_nested_type_with_no_modifier_is_private(self):
        assert not cs_api.is_public(typ("Inner", mods=(), outer="Outer"), [typ("Outer")], [])

    def test_partial_type_is_public_when_any_part_says_so(self):
        part_b = typ("Totals", mods=(), partial=True)

        assert cs_api.is_public(part_b, [], [typ("Totals", partial=True), part_b])
        assert not cs_api.is_public(part_b, [], [part_b])

    def test_member_of_a_partial_part_without_public_is_public_through_another_part(self):
        part_b = typ("Totals", mods=(), partial=True)

        assert cs_api.is_public(member("Total"), [part_b], [typ("Totals", partial=True), part_b])


class TestItems:
    def core(self, **kw):
        return rows([project(files=["a.cs", "b.cs", "c.cs", "d.cs", "poly.cs"], **kw)], CORE)

    def test_public_types_and_members_are_listed(self):
        found, _, _ = self.core()

        assert {"Order", "IClock", "IClock.Now", "Outer", "Outer.Inner", "Outer.P", "Hidden", "Totals", "Totals.Total", "Money"} <= set(found)

    def test_non_public_names_are_left_out(self):
        found, _, _ = self.core()

        assert not {"Secret", "Outer.Q", "CallerArgumentExpressionAttribute"} & set(found)

    def test_overloads_are_one_row(self):
        found, _, _ = self.core()

        assert found["Money.Round"]["symbol_kind"] == "method (2 overloads)"

    def test_extension_method_has_its_own_kind(self):
        found, _, _ = self.core()

        assert found["Money.Shout"]["symbol_kind"] == "extension method"

    def test_hidden_type_says_so_in_the_audience(self):
        found, _, _ = self.core()

        assert found["Hidden"]["audience"] == "packable, hidden from editors"
        assert found["Order"]["audience"] == "packable"

    def test_obsolete_is_named_in_the_audience(self):
        decls = {"a.cs": file(typ("Old", attrs=[("Obsolete", '"no"')]))}

        found, _, _ = rows([project(files=["a.cs"])], decls)

        assert found["Old"]["audience"] == "packable, obsolete"

    def test_partial_type_is_one_row_from_its_first_file(self):
        symbols, _, _ = cs_api.items([project(files=["a.cs", "b.cs", "c.cs", "d.cs", "poly.cs"])], CORE, set())

        assert [s["path"] for s in symbols if s["name"] == "Totals"] == ["c.cs"]

    def test_row_carries_package_namespace_and_position(self):
        found, _, _ = self.core()

        assert (found["Order"]["package"], found["Order"]["subpath"], found["Order"]["line"], found["Order"]["kind"]) == ("Shop.Core", "Shop.Core", 3, "public-api")

    def test_package_falls_back_to_the_assembly_then_the_name(self):
        p = project(files=["a.cs"], package_id=None)
        p["package_id"] = None

        found, _, _ = rows([p], CORE)

        assert found["Order"]["package"] == "Shop.Core"

    def test_non_packable_and_test_projects_have_no_rows(self):
        assert rows([project(files=["a.cs"], packable=False)], CORE)[0] == {}
        assert rows([project(files=["a.cs"], packable=False, test=True)], CORE)[0] == {}

    def test_generated_files_are_left_out(self):
        found, _, _ = rows([project(files=["a.cs"])], CORE, generated={"a.cs"})

        assert found == {}

    def test_protected_member_of_a_sealed_class_is_not_listed(self):
        decls = {"a.cs": file(typ("S", [member("P", mods=("protected",)), member("Q")], mods=("public", "sealed")))}

        found, _, _ = rows([project(files=["a.cs"])], decls)

        assert "S.P" not in found and "S.Q" in found

    def test_protected_member_of_a_static_class_is_not_listed(self):
        decls = {"a.cs": file(typ("S", [member("P", mods=("protected",))], mods=("public", "static")))}

        assert "S.P" not in rows([project(files=["a.cs"])], decls)[0]

    def test_record_positional_parameters_are_properties(self):
        decls = {"a.cs": file(typ("R", kind="record", params=["Id", "Name"]))}

        found, _, _ = rows([project(files=["a.cs"])], decls)

        assert found["R.Id"]["symbol_kind"] == "property"

    def test_constructors_are_listed(self):
        decls = {"a.cs": file(typ("C", [member("C", kind="constructor")]))}

        found, _, _ = rows([project(files=["a.cs"])], decls)

        assert found["C.C"]["symbol_kind"] == "constructor"

    def test_each_packable_project_has_its_own_rows(self):
        data = file(typ("Repo", ns="Shop.Data"))
        projects = [project("Shop.Core", files=["a.cs"]), project("Shop.Data", files=["x.cs"]), project("Shop.Api", files=["y.cs"], packable=False)]

        symbols, _, _ = cs_api.items(projects, {**CORE, "x.cs": data, "y.cs": file(typ("Program"))}, set())

        assert {(s["package"], s["name"]) for s in symbols if s["name"] in ("Repo", "Program")} == {("Shop.Data", "Repo")}

    def test_friend_line_for_each_project_and_friend(self):
        _, _, friends = self.core(friends=["Shop.Tests"])

        assert friends == [{"project": "Shop.Core", "friend": "Shop.Tests"}]

    def test_file_that_could_not_be_parsed_gives_a_note(self):
        _, notes, _ = rows([project(files=["a.cs", "missing.cs"])], CORE)

        assert notes == [{"kind": "cs-note", "path": "src/Shop.Core/Shop.Core.csproj", "note": "api", "name": "Shop.Core"}]


class TestDefPublic:
    def test_each_declaration_gets_its_per_file_flag(self):
        flags = cs_api.line_flags(CORE["a.cs"])

        by_name = {(n, line): pub for n, line, _, pub in flags}
        assert by_name[("Order", 3)] and not by_name[("Secret", 3)] and not by_name[("Q", 5)] and by_name[("P", 5)]
