import base64
import hashlib
import io
import types
import zipfile

import pytest

import cs_scip
import scip_read
import shared_tools
import toolcheck


def make_nupkg(members=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in (members or {"tools/net10.0/any/scip-dotnet.dll": b"dll", "tools/net8.0/any/scip-dotnet.dll": b"dll8"}).items():
            z.writestr(name, data)
    return buf.getvalue()


def tool_for(data):
    sha = base64.b64encode(hashlib.sha512(data).digest()).decode()
    return {"id": "scip-dotnet", "version": "0.2.16", "nupkg": {"url": "https://example.invalid/x.nupkg", "sha512": sha}}


class Fetch:
    def __init__(self, data):
        self.data = data
        self.calls = 0

    def __call__(self, url, dest, timeout):
        self.calls += 1
        dest.write_bytes(self.data)


class TestInstallDir:
    def test_path_sits_under_the_tools_cache_with_the_version(self, tmp_path):
        folder = cs_scip.install_dir(tmp_path, "0.2.16")

        assert folder == tmp_path / ".dossier-tools" / "dotnet" / "scip-dotnet-0.2.16"


class TestEnsureInstalled:
    def test_right_bytes_install_and_write_the_marker(self, tmp_path):
        data = make_nupkg()

        folder = cs_scip.ensure_installed(tmp_path, tool_for(data), 30, fetch=Fetch(data))

        assert (folder / "tools/net10.0/any/scip-dotnet.dll").read_bytes() == b"dll"
        assert (folder / ".installed").read_text().strip() == tool_for(data)["nupkg"]["sha512"]

    def test_second_call_does_not_fetch_again(self, tmp_path):
        data = make_nupkg()
        fetch = Fetch(data)
        cs_scip.ensure_installed(tmp_path, tool_for(data), 30, fetch=fetch)

        cs_scip.ensure_installed(tmp_path, tool_for(data), 30, fetch=fetch)

        assert fetch.calls == 1

    def test_wrong_bytes_raise_the_checksum_error_and_leave_nothing(self, tmp_path):
        tool = tool_for(make_nupkg())

        with pytest.raises(shared_tools.ToolError, match="did not match its pinned checksum"):
            cs_scip.ensure_installed(tmp_path, tool, 30, fetch=Fetch(b"not the package"))

        assert not cs_scip.install_dir(tmp_path, "0.2.16").exists()

    def test_member_with_dotdot_is_refused(self, tmp_path):
        data = make_nupkg({"../x": b"evil"})

        with pytest.raises(shared_tools.ToolError):
            cs_scip.ensure_installed(tmp_path, tool_for(data), 30, fetch=Fetch(data))

        assert not (tmp_path / ".dossier-tools" / "dotnet" / "x").exists()

    def test_absolute_member_is_refused(self, tmp_path):
        data = make_nupkg({"/etc/x": b"evil"})

        with pytest.raises(shared_tools.ToolError):
            cs_scip.ensure_installed(tmp_path, tool_for(data), 30, fetch=Fetch(data))


class TestToolDll:
    def build(self, tmp_path):
        data = make_nupkg()
        return cs_scip.ensure_installed(tmp_path, tool_for(data), 30, fetch=Fetch(data))

    def test_highest_installed_runtime_wins(self, tmp_path):
        folder = self.build(tmp_path)

        assert cs_scip.tool_dll(folder, [8, 10]) == folder / "tools/net10.0/any/scip-dotnet.dll"

    def test_only_eight_gives_net8(self, tmp_path):
        folder = self.build(tmp_path)

        assert cs_scip.tool_dll(folder, [8]) == folder / "tools/net8.0/any/scip-dotnet.dll"

    def test_unsupported_runtime_gives_none(self, tmp_path):
        folder = self.build(tmp_path)

        assert cs_scip.tool_dll(folder, [7]) is None


class TestPinnedEntry:
    def entry(self):
        return {t["id"]: t for t in toolcheck.load_tools()["tools"]}["scip-dotnet"]

    def test_pin_is_the_gated_release(self):
        e = self.entry()

        assert (e["version"], e["published"]) == ("0.2.16", "2026-10-21")
        assert e["nupkg"]["sha512"].startswith("UUaPQCnqIWFYGXaKtgjieBP0WR0uH8L55pwqhtOJH")

    def test_cards_are_filled(self):
        assert self.entry()["cards"] == ["components.catalog", "interactions.flows", "interactions.graph"]

    def test_package_list_is_marked_not_run(self):
        e = {t["id"]: t for t in toolcheck.load_tools()["tools"]}["dotnet-package-list"]

        assert e["open"].startswith("Not run:")


class TestDoctorText:
    def test_hash_checked_package_is_named(self):
        report = toolcheck.preflight(["C#"], path="/nonexistent")
        text = toolcheck.format_text(report)

        assert "scip-dotnet 0.2.16 from a hash-checked NuGet package" in text


PKG = "scip-dotnet nuget . . "


def occ(symbol, roles=1, line=0):
    return {"range": [line, 0, line, 5], "symbol": PKG + symbol, "roles": roles, "enclosing_range": [line, 0, line + 2, 1]}


def doc(path, *occurrences):
    return {"path": path, "occurrences": list(occurrences), "symbols": []}


def types_of(*pairs):
    """decls for disambiguate: {path: {"types": [...]}} from (path, name, partial) triples."""
    out: dict = {}
    for path, name, partial in pairs:
        out.setdefault(path, {"types": []})["types"].append(
            {"name": name, "kind": "class", "partial": partial, "modifiers": ["public"], "members": [], "line": 1, "end_line": 9, "outer": None, "namespace": "N"})
    return out


class TestJoin:
    def test_first_seen_document_wins(self):
        a = {"documents": [doc("x.cs", occ("N/A#"))]}
        b = {"documents": [doc("x.cs", occ("N/B#")), doc("y.cs")]}

        joined = cs_scip.join([a, b])

        assert [d["path"] for d in joined["documents"]] == ["x.cs", "y.cs"]
        assert joined["documents"][0]["occurrences"][0]["symbol"].endswith("N/A#")

    def test_documents_that_are_not_tracked_are_dropped(self):
        a = {"documents": [doc("src/x.cs"), doc("src/obj/Debug/x.g.cs")]}

        joined = cs_scip.join([a], tree={"src/x.cs"})

        assert [d["path"] for d in joined["documents"]] == ["src/x.cs"]


class TestDisambiguate:
    def two_docs(self, symbol="N/Item#"):
        return {"documents": [doc("a.cs", occ(symbol)), doc("b.cs", occ(symbol), occ(symbol, roles=0, line=3))]}

    def test_partial_type_defined_in_two_files_is_kept(self):
        index = {"documents": [doc("a.cs", occ("N/Totals#")), doc("b.cs", occ("N/Totals#"))]}

        out, count = cs_scip.disambiguate(index, types_of(("a.cs", "Totals", True), ("b.cs", "Totals", True)))

        assert count == 0 and out["documents"][1]["occurrences"][0]["symbol"] == PKG + "N/Totals#"

    def test_member_of_a_partial_type_defined_twice_is_kept(self):
        index = {"documents": [doc("a.cs", occ("N/Totals#Run().")), doc("b.cs", occ("N/Totals#Run()."))]}

        _, count = cs_scip.disambiguate(index, types_of(("a.cs", "Totals", True), ("b.cs", "Totals", True)))

        assert count == 0

    def test_same_name_in_two_different_types_becomes_local_and_is_counted(self):
        index = self.two_docs()

        out, count = cs_scip.disambiguate(index, types_of(("a.cs", "Item", False), ("b.cs", "Item", False)))

        symbols = {o["symbol"] for d in out["documents"] for o in d["occurrences"]}
        assert count == 1 and all(s.startswith("local ambiguous-") for s in symbols)

    def test_partial_in_one_file_only_is_still_ambiguous(self):
        index = self.two_docs()

        _, count = cs_scip.disambiguate(index, types_of(("a.cs", "Item", True), ("b.cs", "Item", False)))

        assert count == 1

    def test_ambiguous_symbols_give_no_defs_after_reduce(self):
        out, _ = cs_scip.disambiguate(self.two_docs(), types_of(("a.cs", "Item", False), ("b.cs", "Item", False)))

        assert scip_read.reduce(out) == []

    def test_symbol_defined_once_is_untouched(self):
        index = {"documents": [doc("a.cs", occ("N/A#")), doc("b.cs", occ("N/A#", roles=0))]}

        out, count = cs_scip.disambiguate(index, types_of(("a.cs", "A", False)))

        assert count == 0 and out == index


def item(symbol, path="a.cs", line=3, name=None):
    return {"kind": "def", "path": path, "line": line, "end_line": line + 1, "name": name or symbol, "symbol": PKG + symbol, "type": "class", "public": True, "refs": 0}


class TestFinishSymbols:
    def decls(self):
        return {"a.cs": {"types": [{"name": "Secret", "kind": "class", "modifiers": ["internal"], "line": 3, "end_line": 9, "attributes": [], "outer": None,
                                    "partial": False, "namespace": "N", "params": [], "members": []},
                                   {"name": "Order", "kind": "class", "modifiers": ["public"], "line": 11, "end_line": 20, "attributes": [], "outer": None,
                                    "partial": False, "namespace": "N", "params": [], "members": []}]}}

    def test_parameter_definitions_are_dropped(self):
        rows = [item("N/Order#Greet().(name)", line=12), item("N/Order#Greet().", line=12)]

        out = cs_scip.finish_symbols(rows, self.decls(), set())

        assert [r["symbol"] for r in out] == [PKG + "N/Order#Greet()."]

    def test_type_parameter_definitions_are_dropped(self):
        out = cs_scip.finish_symbols([item("N/Order#[T]", line=11), item("N/Order#", line=11)], self.decls(), set())

        assert [r["symbol"] for r in out] == [PKG + "N/Order#"]

    def test_public_flag_comes_from_the_declaration(self):
        rows = [item("N/Secret#", line=3, name="Secret"), item("N/Order#", line=11, name="Order")]

        out = {r["name"]: r["public"] for r in cs_scip.finish_symbols(rows, self.decls(), set())}

        assert out == {"Secret": False, "Order": True}

    def test_definition_with_no_matching_declaration_is_not_public(self):
        out = cs_scip.finish_symbols([item("N/Ghost#", path="z.cs", name="Ghost")], self.decls(), set())

        assert out[0]["public"] is False

    def test_definitions_in_generated_files_are_dropped(self):
        out = cs_scip.finish_symbols([item("N/Order#", line=11, name="Order")], self.decls(), {"a.cs"})

        assert out == []

    def test_reference_edges_pass_through(self):
        edge = {"kind": "ref-edge", "path": "a.cs", "paths": ["b.cs"], "count": 2}

        assert cs_scip.finish_symbols([edge], self.decls(), set()) == [edge]


class TestFallbackDefs:
    def decls(self):
        t = {"name": "Order", "kind": "class", "modifiers": ["public"], "line": 3, "end_line": 9, "attributes": [], "outer": None, "partial": False,
             "namespace": "Shop.Core", "params": [],
             "members": [{"name": "Total", "kind": "method", "modifiers": ["public"], "line": 5, "end_line": 6, "attributes": [], "params": []},
                         {"name": "Total", "kind": "method", "modifiers": ["public"], "line": 7, "end_line": 8, "attributes": [], "params": []}]}
        return {"a.cs": {"types": [t]}, "g.cs": {"types": [{**t, "name": "Gen"}]}}

    def test_symbols_have_no_line_numbers(self):
        rows = cs_scip.fallback_defs(self.decls(), {"g.cs"})

        assert [r["symbol"] for r in rows] == ["cs Shop.Core/Order#", "cs Shop.Core/Order#Total"]

    def test_rows_are_marked_as_tree_sitter_with_no_references(self):
        row = cs_scip.fallback_defs(self.decls(), {"g.cs"})[0]

        assert (row["kind"], row["via"], row["refs"], row["public"], row["type"], row["name"]) == ("def", "tree-sitter", 0, True, "class", "Order")

    def test_generated_files_give_nothing(self):
        assert cs_scip.fallback_defs(self.decls(), {"g.cs", "a.cs"}) == []


class FakeRun:
    def __init__(self, tmp_path, returncode=0, out="", err="", write=True):
        self.tmp, self.rc, self.out, self.err, self.write = tmp_path, returncode, out, err, write
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append((cmd, kw))
        if self.write:
            target = cmd[cmd.index("--output") + 1]
            open(target, "wb").write(b"x")
        o, e = self.tmp / "out.txt", self.tmp / "err.txt"
        o.write_text(self.out)
        e.write_text(self.err)
        return types.SimpleNamespace(returncode=self.rc, timed_out=self.rc is None, stdout=o, stderr=e)


class TestScipDotnetIndex:
    def test_command_has_the_working_directory_the_output_and_no_restore(self, tmp_path):
        run = FakeRun(tmp_path)
        area = tmp_path / "area"

        path, rc, _ = cs_scip.ScipDotnet(run, "/x/scip-dotnet.dll", 60).index(tmp_path / "co", "Shop.slnx", area, 2)

        cmd, kw = run.calls[0]
        assert cmd[:4] == ["dotnet", "/x/scip-dotnet.dll", "index", "Shop.slnx"]
        assert cmd[cmd.index("--working-directory") + 1] == str(tmp_path / "co") and "--skip-dotnet-restore" in cmd
        assert path == area / "scip" / "cs-2.scip" and rc == 0
        assert (kw["profile"], kw["cwd"], kw["timeout"]) == ("restricted", tmp_path / "co", 60)

    def test_log_joins_stdout_and_stderr(self, tmp_path):
        run = FakeRun(tmp_path, out="Failure: a", err="warn b")

        _, _, log = cs_scip.ScipDotnet(run, "d", 1).index(tmp_path, "x.slnx", tmp_path / "area", 0)

        assert "Failure: a" in log and "warn b" in log

    def test_old_index_is_removed_first(self, tmp_path):
        area = tmp_path / "area"
        (area / "scip").mkdir(parents=True)
        (area / "scip" / "cs-0.scip").write_bytes(b"old")
        run = FakeRun(tmp_path, returncode=1, write=False)

        path, _, _ = cs_scip.ScipDotnet(run, "d", 1).index(tmp_path, "x.slnx", area, 0)

        assert not path.exists()


class TestFailure:
    def written(self, tmp_path, size=1):
        p = tmp_path / "i.scip"
        p.write_bytes(b"x" * size)
        return p

    def test_exit_one_is_a_failure_with_the_last_line(self, tmp_path):
        assert cs_scip.failure(1, "a\nboom\n", tmp_path / "none.scip") == "boom"

    def test_exit_one_prefers_the_first_failure_line(self, tmp_path):
        assert cs_scip.failure(1, "x\nFailure: bad project\nlast", tmp_path / "n.scip") == "Failure: bad project"

    def test_timeout_is_a_failure(self, tmp_path):
        assert "too long" in cs_scip.failure(None, "", self.written(tmp_path))

    def test_missing_index_is_a_failure(self, tmp_path):
        assert cs_scip.failure(0, "", tmp_path / "none.scip") == "scip-dotnet finished without writing an index."

    def test_empty_index_is_a_failure(self, tmp_path):
        assert cs_scip.failure(0, "", self.written(tmp_path, 0)) == "scip-dotnet finished without writing an index."

    def test_clean_run_is_not_a_failure(self, tmp_path):
        assert cs_scip.failure(0, "fine", self.written(tmp_path)) is None

    def test_exit_zero_with_failure_lines_is_not_a_hard_failure(self, tmp_path):
        assert cs_scip.failure(0, "Failure: x", self.written(tmp_path)) is None


class TestSoftFailure:
    def test_first_failure_line_is_returned_without_its_label(self):
        assert cs_scip.soft_failure("ok\nFailure: App.csproj could not load\nFailure: other") == "App.csproj could not load"

    def test_no_failure_lines_gives_none(self):
        assert cs_scip.soft_failure("all good") is None


def tdecl(name, mods=("internal",), kind="class", bases=(), line=3, end=9):
    return {"name": name, "kind": kind, "modifiers": list(mods), "line": line, "end_line": end, "attributes": [], "bases": list(bases), "partial": False,
            "outer": None, "namespace": "N", "params": [], "members": []}


def dead(types, defs=None, entries=(), models=(), blindspots=(), generated=(), tests=(), idents=None, path="a.cs"):
    decls = {path: {"types": types, "idents": idents or {}}}
    defs = [item(f"N/{t['name']}#", path=path, line=t["line"], name=t["name"]) | {"public": "public" in t["modifiers"]} for t in types] if defs is None else defs
    return cs_scip.dead_items(defs, decls, list(entries), list(models), list(blindspots), set(generated), set(tests))


class TestDeadItems:
    def test_internal_type_with_no_references_is_listed(self):
        rows = dead([tdecl("Secret")])

        assert [(r["name"], r["rule"], r["type"], r["confidence"]) for r in rows] == [("Secret", "scip-dotnet.unused-type", "dead code without references", None)]

    def test_row_points_at_the_declaration(self):
        row = dead([tdecl("Secret", line=4, end=8)])[0]

        assert (row["path"], row["line"], row["end_line"]) == ("a.cs", 4, 8)

    def test_referenced_type_is_not_listed(self):
        defs = [item("N/Secret#", name="Secret") | {"refs": 2, "public": False}]

        assert dead([tdecl("Secret")], defs=defs) == []

    def test_public_type_is_not_listed(self):
        assert dead([tdecl("Order", mods=("public",))]) == []

    def test_type_with_no_definition_in_the_index_is_not_listed(self):
        assert dead([tdecl("Secret")], defs=[]) == []

    def test_interface_and_enum_are_not_listed(self):
        assert dead([tdecl("I", kind="interface"), tdecl("E", kind="enum")]) == []

    def test_record_and_struct_are_listed(self):
        assert [r["name"] for r in dead([tdecl("R", kind="record"), tdecl("S", kind="struct")])] == ["R", "S"]

    @pytest.mark.parametrize("pattern", ["di-registration", "di-scan", "mediator-handler", "mvc-filter", "route-convention", "reflection"])
    def test_file_with_a_dynamic_use_hit_is_not_listed(self, pattern):
        assert dead([tdecl("Secret")], blindspots=[{"path": "a.cs", "pattern": pattern}]) == []

    def test_other_blind_spots_do_not_hide_it(self):
        assert dead([tdecl("Secret")], blindspots=[{"path": "a.cs", "pattern": "partial-class"}])

    def test_entity_is_not_listed(self):
        assert dead([tdecl("Secret")], models=[{"path": "a.cs", "name": "Secret", "kind": "ef-entity"}]) == []

    def test_entry_point_inside_the_type_hides_it(self):
        assert dead([tdecl("Secret", line=3, end=9)], entries=[{"path": "a.cs", "line": 5, "kind": "http-route"}]) == []

    def test_generated_and_test_files_are_not_listed(self):
        assert dead([tdecl("Secret")], generated=["a.cs"]) == [] and dead([tdecl("Secret")], tests=["a.cs"]) == []

    def test_type_with_a_base_from_outside_the_repository_is_not_listed(self):
        assert dead([tdecl("Secret", bases=["ControllerBase"])]) == []

    def test_type_with_a_base_declared_in_the_repository_is_listed(self):
        rows = dead([tdecl("Base", mods=("public",)), tdecl("Secret", bases=["Base"], line=12, end=18)])

        assert [r["name"] for r in rows] == ["Secret"]

    def test_generic_base_is_matched_by_its_name(self):
        assert dead([tdecl("Secret", bases=["Handler<int>"])]) == []

    def test_name_used_elsewhere_in_its_own_file_hides_it(self):
        assert dead([tdecl("Secret", line=3, end=9)], idents={"Secret": [3, 12]}) == []

    def test_name_only_inside_its_own_span_does_not_hide_it(self):
        assert dead([tdecl("Secret", line=3, end=9)], idents={"Secret": [3, 5]})
