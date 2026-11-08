import cs_semgrep


def hit(rule, detail=None, snippet="x", path="a.cs", line=3, **meta):
    return {"rule": f"dossier.csharp.{rule}", "path": path, "start_line": line, "end_line": line, "snippet": snippet, "detail": detail, "metadata": meta}


class TestRouteName:
    def test_verbs_are_upper_cased_and_map_is_any(self):
        assert [cs_semgrep.route_name(d, "s") for d in ('MapGet("/health', 'MapPost("/o', 'MapDelete("/x/{id}', 'Map("/y', 'MapMethods("/z')] == [
            "GET /health", "POST /o", "DELETE /x/{id}", "ANY /y", "ANY /z"]

    def test_fallback_has_its_own_name(self):
        assert cs_semgrep.route_name("MapFallback", "s") == "ANY (fallback)"

    def test_no_detail_falls_back_to_the_snippet(self):
        assert cs_semgrep.route_name(None, "app.MapGet(path, h);") == "app.MapGet(path, h);"


class TestItems:
    def test_a_minimal_route_is_an_entry_point(self):
        got = cs_semgrep.items([hit("entry.minimal-route", 'MapGet("/health', category="entry", kind="http-route")])["entry_points"][0]

        assert (got["kind"], got["name"], got["trigger"], got["snippet"], got["target"], got["rule"]) == (
            "http-route", "GET /health", "a web request to `GET /health`", "GET /health", "a.cs", "dossier.csharp.entry.minimal-route")

    def test_the_other_entry_kinds_have_their_triggers(self):
        rows = [hit("entry.map-hub", "/chat", category="entry", kind="signalr-hub"), hit("entry.map-grpc", "Greeter", category="entry", kind="grpc-service"),
                hit("entry.add-hosted", "Cleanup", category="entry", kind="hosted-service"), hit("entry.hangfire", "nightly", category="entry", kind="scheduled-job"),
                hit("entry.cli-command", "serve", category="entry", kind="cli-command")]

        got = [(e["name"], e["trigger"]) for e in cs_semgrep.items(rows)["entry_points"]]

        assert got == [("/chat", "a SignalR connection to `/chat`"), ("Greeter", "a gRPC call to `Greeter`"), ("Cleanup", "when the host starts"),
                       ("nightly", "a schedule"), ("serve", "the `serve` command")]

    def test_a_build_target_is_kept_only_in_a_build_project_and_names_it(self):
        row = hit("entry.bullseye-target", "default", path="build/Program.cs", category="entry", kind="build-target")
        project_of = lambda p: "build/build.csproj"  # noqa: E731

        kept = cs_semgrep.items([row], project_of, {"build/build.csproj"})["entry_points"]
        dropped = cs_semgrep.items([row], project_of, set())["entry_points"]

        assert [e["trigger"] for e in kept] == ["running `dotnet run --project build/build.csproj -- default`"] and dropped == []

    def test_io_findings_keep_their_category_and_detail(self):
        got = cs_semgrep.items([hit("inputs.env-var", "SHOP_KEY", category="env-var")])["io_candidates"]

        assert got == [{"path": "a.cs", "line": 3, "end_line": 3, "rule": "dossier.csharp.inputs.env-var", "snippet": "x", "category": "env-var", "detail": "SHOP_KEY"}]

    def test_a_request_header_gets_one_row_whatever_the_case(self):
        rows = [hit("inputs.request-header", "X-Tenant", line=1, category="request-header"), hit("inputs.request-header", "x-tenant", line=2, category="request-header"),
                hit("inputs.request-header", "X-Other", line=3, category="request-header")]

        assert [i["detail"] for i in cs_semgrep.items(rows)["io_candidates"]] == ["X-Tenant", "X-Other"]

    def test_a_blind_spot_keeps_its_pattern(self):
        got = cs_semgrep.items([hit("blindspot.di-scan", category="blindspot", pattern="di-scan")])["blindspots"]

        assert got[0]["pattern"] == "di-scan" and got[0]["rule"] == "dossier.csharp.blindspot.di-scan"
