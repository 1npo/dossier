import cs_queries


def cap(capture, text, start, end=None):
    return {"path": "a.cs", "capture": capture, "text": text, "start_line": start, "end_line": end or start + text.count("\n"), "start_col": 0}


def one(*caps):
    return cs_queries.assemble({"a.cs": list(caps)})["a.cs"]


class TestNamespaces:
    def test_a_file_scoped_namespace_holds_the_types_after_it(self):
        d = one(cap("ns", "namespace Shop.Api;", 1), cap("type", "public class A\n{\n}", 3))

        assert d["types"][0]["namespace"] == "Shop.Api"

    def test_block_namespaces_nest_into_a_dotted_name(self):
        d = one(cap("ns", "namespace A\n{\n namespace B\n {\n class C { }\n }\n}", 1, 7),
                cap("ns", "namespace B\n {\n class C { }\n }", 3, 6), cap("type", "class C { }", 5))

        assert [n["name"] for n in d["namespaces"]] == ["A", "A.B"]
        assert d["types"][0]["namespace"] == "A.B"


class TestUsings:
    def test_global_static_and_alias_usings(self):
        d = one(cap("using", "global using System.Linq;", 1), cap("using", "using static System.Math;", 2),
                cap("using", "using Json = System.Text.Json;", 3), cap("using", "using Shop.Core;", 4))

        assert [(u["name"], u["global"], u["static"], u["alias"]) for u in d["usings"]] == [
            ("System.Linq", True, False, None), ("System.Math", False, True, None),
            ("System.Text.Json", False, False, "Json"), ("Shop.Core", False, False, None)]


class TestTypes:
    def test_modifiers_kind_and_partial(self):
        d = one(cap("type", "public sealed partial class Totals\n{\n}", 3))

        t = d["types"][0]
        assert (t["name"], t["kind"], t["modifiers"], t["partial"]) == ("Totals", "class", ["public", "sealed", "partial"], True)

    def test_a_base_list_splits_outside_angle_brackets_and_drops_constraints(self):
        d = one(cap("type", "public class Repo<T> : Base<T, int>, IRepo<T> where T : class\n{\n}", 1))

        assert d["types"][0]["bases"] == ["Base<T, int>", "IRepo<T>"]

    def test_a_primary_constructor_base_loses_its_arguments(self):
        d = one(cap("type", "public record Big(int A) : Small(A);", 1))

        assert d["types"][0]["bases"] == ["Small"]

    def test_record_positional_parameters_become_properties(self):
        d = one(cap("type", "public record Money(decimal Amount, string Currency);", 1))

        t = d["types"][0]
        assert t["kind"] == "record"
        assert [(m["name"], m["kind"], m["type"]) for m in t["members"]] == [("Amount", "property", "decimal"), ("Currency", "property", "string")]

    def test_a_nested_type_names_its_outer_type(self):
        d = one(cap("type", "public class Outer\n{\n public class Inner { }\n}", 1, 4), cap("type", "public class Inner { }", 3))

        assert [(t["name"], t["outer"]) for t in d["types"]] == [("Outer", None), ("Inner", "Outer")]

    def test_a_type_with_no_modifier_has_an_empty_list(self):
        assert one(cap("type", "interface IClock\n{\n}", 1))["types"][0]["modifiers"] == []

    def test_attributes_on_a_type_keep_their_arguments_and_lines(self):
        d = one(cap("type", '[ApiController]\n[Route("api/[controller]")]\npublic class C : ControllerBase\n{\n}', 5))

        assert [(a["name"], a["args"], a["line"]) for a in d["types"][0]["attributes"]] == [("ApiController", "", 5), ("Route", '"api/[controller]"', 6)]


class TestMembers:
    def _members(self, *members):
        d = one(cap("type", "public class C\n{\n}", 1, 20), *members)
        return {m["name"]: m for m in d["types"][0]["members"]}

    def test_two_attribute_lists_on_one_method_both_belong_to_it(self):
        got = self._members(cap("member.method", '[HttpGet("{id}")]\n[Authorize]\npublic IActionResult Get(int id) => Ok();', 3))

        assert [a["name"] for a in got["Get"]["attributes"]] == ["HttpGet", "Authorize"]
        assert got["Get"]["params"] == [{"name": "id", "type": "int", "this": False}]
        assert got["Get"]["type"] == "IActionResult"

    def test_an_attribute_with_a_target_or_the_attribute_suffix_loses_both(self):
        got = self._members(cap("member.method", "[Obsolete]\n[return: NotNull]\npublic void M() { }", 3))

        assert [a["name"] for a in got["M"]["attributes"]] == ["Obsolete", "NotNull"]
        assert cs_queries.strings_in('"a", Name = "b"') == ["a", "b"]

    def test_the_this_parameter_marks_an_extension_method(self):
        got = self._members(cap("member.method", "public static int Twice(this int x, int y = 2) { }", 3))

        assert [(p["name"], p["this"]) for p in got["Twice"]["params"]] == [("x", True), ("y", False)]
        assert got["Twice"]["static"] is True

    def test_a_generic_method_name_has_no_type_parameters(self):
        got = self._members(cap("member.method", "public T Get<T>(int id) where T : class { }", 3))

        assert (got["Get"]["name"], got["Get"]["type"]) == ("Get", "T")

    def test_a_constructor_has_no_type(self):
        got = self._members(cap("member.constructor", "public C(IClock clock) { }", 3))

        assert (got["C"]["kind"], got["C"]["type"], len(got["C"]["params"])) == ("constructor", None, 1)

    def test_a_property_knows_whether_it_can_be_read(self):
        got = self._members(cap("member.property", "public List<Order> Orders { get; set; }", 3), cap("member.property", "public int Count { set; }", 4),
                            cap("member.property", "public int Twice => 2;", 5))

        assert (got["Orders"]["type"], got["Orders"]["get"], got["Count"]["get"], got["Twice"]["get"]) == ("List<Order>", True, False, True)

    def test_a_field_keeps_its_initialiser_and_staticness(self):
        got = self._members(cap("member.field", "private static readonly Dictionary<string, int> _cache = new();", 3),
                            cap("member.field", "private int _count;", 4))

        assert (got["_cache"]["type"], got["_cache"]["static"], got["_cache"]["init"]) == ("Dictionary<string, int>", True, "new()")
        assert got["_count"]["init"] == "" and got["_count"]["static"] is False

    def test_an_interface_member_has_no_modifier(self):
        d = one(cap("type", "public interface IClock\n{\n DateTime Now();\n}", 1, 4), cap("member.method", "DateTime Now();", 3))

        assert d["types"][0]["members"][0]["modifiers"] == []

    def test_enum_members_are_listed(self):
        d = one(cap("type", "public enum S\n{\n A,\n B = 2\n}", 1, 5), cap("member.enum-member", "A", 3), cap("member.enum-member", "B = 2", 4))

        assert [m["name"] for m in d["types"][0]["members"]] == ["A", "B"]


class TestFileFacts:
    def test_a_global_statement_marks_top_level_code(self):
        assert one(cap("global", "var x = 1;", 1))["top_level"] is True
        assert one()["top_level"] is False

    def test_an_assembly_attribute_is_kept(self):
        d = one(cap("attrlist", '[assembly: InternalsVisibleTo("Shop.Tests")]', 1))

        assert [(a["name"], a["args"]) for a in d["assembly_attributes"]] == [("InternalsVisibleTo", '"Shop.Tests"')]

    def test_only_capitalised_identifiers_are_kept_with_every_line(self):
        d = one(cap("ident", "Order", 4), cap("ident", "order", 4), cap("ident", "Order", 9))

        assert d["idents"] == {"Order": [4, 9]}
