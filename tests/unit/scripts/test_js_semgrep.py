import js_semgrep


def result(rule, detail=None, snippet="x", **meta):
    return {"rule": rule, "path": "src/a.ts", "start_line": 3, "end_line": 4, "snippet": snippet, "detail": detail, "metadata": meta}


class TestScannable:
    def test_declaration_files_are_left_out_and_mts_and_cts_are_counted_as_skipped(self):
        ok, skipped = js_semgrep.scannable(["a.ts", "b.tsx", "c.d.ts", "d.mts", "e.cts", "f.d.mts", "g.js", "h.json"])

        assert (ok, skipped) == (["a.ts", "b.tsx", "g.js"], ["d.mts", "e.cts"])


class TestItems:
    def test_an_http_route_is_named_by_method_and_path_and_the_snippet_is_the_name(self):
        out = js_semgrep.items([result("dossier.js.entry.http-route", "get('/tags", "router.get(", category="entry", kind="http-route")])

        item = out["entry_points"][0]
        assert (item["kind"], item["name"], item["snippet"], item["trigger"]) == ("http-route", "GET /tags", "GET /tags", "a web request to `GET /tags`")

    def test_a_route_chain_has_no_method_so_the_name_is_the_path(self):
        out = js_semgrep.items([result("dossier.js.entry.route-chain", "/cart", category="entry", kind="http-route")])

        assert out["entry_points"][0]["name"] == "/cart"

    def test_a_nest_route_gets_an_upper_case_method(self):
        out = js_semgrep.items([result("dossier.js.entry.nest-route", "Post('users", category="entry", kind="http-route")])

        assert out["entry_points"][0]["name"] == "POST users"

    def test_static_files_are_an_http_entry_point_named_static_files(self):
        out = js_semgrep.items([result("dossier.js.entry.static-files", None, "app.use(express.static('a'))", category="entry", kind="http-route")])

        item = out["entry_points"][0]
        assert (item["kind"], item["name"], item["trigger"]) == ("http-route", "static files", "a web request to `static files`")

    def test_a_request_header_keeps_its_category_and_name(self):
        out = js_semgrep.items([result("dossier.js.inputs.request-header", "authorization", category="request-header")])

        assert out["io_candidates"][0]["category"] == "request-header" and out["io_candidates"][0]["detail"] == "authorization"

    def test_server_listen_is_named_listen(self):
        out = js_semgrep.items([result("dossier.js.entry.server-listen", None, "app.listen(3000);", category="entry", kind="server-listen")])

        item = out["entry_points"][0]
        assert (item["name"], item["trigger"]) == ("listen", "when the server starts")

    def test_a_queue_worker_uses_its_detail_as_name(self):
        out = js_semgrep.items([result("dossier.js.entry.queue-worker", "mail", category="entry", kind="queue-consumer")])

        assert out["entry_points"][0]["name"] == "mail"

    def test_an_io_finding_keeps_its_category_and_detail(self):
        out = js_semgrep.items([result("dossier.js.inputs.env-var", "PORT", category="env-var")])

        assert out["io_candidates"] == [{"path": "src/a.ts", "line": 3, "end_line": 4, "rule": "dossier.js.inputs.env-var", "snippet": "x",
                                         "category": "env-var", "detail": "PORT"}]

    def test_a_blind_spot_keeps_its_pattern(self):
        out = js_semgrep.items([result("dossier.js.blindspot.react-context", None, category="blindspot", pattern="react-context")])

        assert out["blindspots"][0]["pattern"] == "react-context"
