import cs_entries


def attr(name, args="", line=1):
    return {"name": name, "args": args, "line": line}


def method(name, attrs=(), mods=("public",), params=(), line=10, static=False):
    return {"name": name, "kind": "method", "modifiers": list(mods), "line": line, "end_line": line, "attributes": list(attrs), "type": "IActionResult",
            "static": static or "static" in mods, "params": list(params)}


def typ(name, members=(), attrs=(), bases=(), mods=("public",), kind="class", line=3):
    return {"name": name, "kind": kind, "modifiers": list(mods), "line": line, "end_line": line + 20, "attributes": list(attrs), "bases": list(bases),
            "partial": False, "outer": None, "namespace": "N", "params": [], "members": list(members)}


def file(*types, top=False, top_line=None):
    return {"namespaces": [], "usings": [], "types": list(types), "top_level": top, "top_level_line": top_line, "idents": {}, "qualified": [], "assembly_attributes": []}


def routes(*types):
    return [(r["name"], r["line"]) for r in cs_entries.controller_routes({"c.cs": file(*types)})]


class TestControllerRoutes:
    def test_prefix_and_template_join_with_a_slash_and_controller_is_replaced(self):
        c = typ("OrdersController", [method("Get", [attr("HttpGet", '"{id}"')])], [attr("ApiController"), attr("Route", '"api/[controller]"')])

        assert routes(c) == [("GET /api/Orders/{id}", 10)]

    def test_a_verb_with_no_template_uses_the_prefix(self):
        c = typ("OrdersController", [method("List", [attr("HttpGet")])], [attr("Route", '"api/orders"')])

        assert routes(c) == [("GET /api/orders", 10)]

    def test_a_template_with_tilde_or_leading_slash_replaces_the_prefix(self):
        c = typ("OrdersController", [method("A", [attr("HttpPost", '"~/submit"')], line=10), method("B", [attr("HttpPut", '"/other"')], line=11)],
                [attr("Route", '"api/x"')])

        assert routes(c) == [("POST /submit", 10), ("PUT /other", 11)]

    def test_action_is_replaced_by_the_method_name(self):
        c = typ("OrdersController", [method("Create", [attr("HttpPost", '"[action]"')])], [attr("Route", '"api/[controller]"')])

        assert routes(c) == [("POST /api/Orders/Create", 10)]

    def test_accept_verbs_gives_one_row_per_verb(self):
        c = typ("XController", [method("M", [attr("AcceptVerbs", '"GET", "POST"'), attr("Route", '"m"')])], [attr("Route", '"api"')])

        assert [r[0] for r in routes(c)] == ["GET /api/m", "POST /api/m"]

    def test_route_with_no_verb_is_any(self):
        c = typ("XController", [method("M", [attr("Route", '"m"')])])

        assert routes(c) == [("ANY /m", 10)]

    def test_a_controller_with_no_attribute_route_gives_no_rows(self):
        c = typ("HomeController", [method("Index")], bases=["Controller"])

        assert routes(c) == []

    def test_non_controller_abstract_and_plain_classes_are_skipped(self):
        m = [method("M", [attr("HttpGet", '"x"')])]

        assert routes(typ("AController", m, [attr("NonController")]), typ("BController", m, mods=("public", "abstract")), typ("Plain", m)) == []

    def test_a_class_is_a_controller_by_base_or_attribute(self):
        m = [method("M", [attr("HttpGet", '"x"')])]

        assert len(routes(typ("A", m, bases=["ControllerBase"]), typ("B", m, [attr("ApiController")]))) == 2

    def test_private_and_static_methods_are_not_actions(self):
        c = typ("XController", [method("P", [attr("HttpGet", '"p"')], mods=("private",)), method("S", [attr("HttpGet", '"s"')], mods=("public", "static"))])

        assert routes(c) == []

    def test_the_item_has_the_entry_fields(self):
        c = typ("OrdersController", [method("Get", [attr("HttpGet", '"x"')])])

        row = cs_entries.controller_routes({"c.cs": file(c)})[0]

        assert row == {"path": "c.cs", "line": 10, "end_line": 10, "kind": "http-route", "name": "GET /x", "trigger": "a web request to `GET /x`", "target": "c.cs",
                       "rule": "cs.controller-route", "snippet": "GET /x"}


def world(*projects):
    return {"projects": list(projects)}


def proj(name, files, test=False):
    return {"path": f"{name}/{name}.csproj", "name": name, "files": list(files), "test": test}


class TestProgramEntries:
    def test_main_in_a_class_gives_program_main_at_the_method(self):
        d = {"L/p.cs": file(typ("Program", [method("Main", mods=("static",), line=5)]))}

        got = cs_entries.program_entries(world(proj("L", ["L/p.cs"])), d)

        assert [(r["kind"], r["name"], r["line"], r["trigger"]) for r in got] == [("program-main", "L", 5, "starting `L` (for example with `dotnet run`)")]

    def test_top_level_statements_give_program_main_at_the_first_statement(self):
        d = {"A/Program.cs": file(top=True, top_line=3)}

        assert [(r["name"], r["line"]) for r in cs_entries.program_entries(world(proj("A", ["A/Program.cs"])), d)] == [("A", 3)]

    def test_test_projects_have_none(self):
        d = {"T/p.cs": file(top=True, top_line=1)}

        assert cs_entries.program_entries(world(proj("T", ["T/p.cs"], test=True)), d) == []

    def test_a_non_static_main_is_not_an_entry(self):
        d = {"L/p.cs": file(typ("Program", [method("Main")]))}

        assert cs_entries.program_entries(world(proj("L", ["L/p.cs"])), d) == []


class TestClassEntries:
    def test_hosted_service_job_and_consumers(self):
        d = {"c.cs": file(typ("Cleanup", bases=["BackgroundService"], line=3), typ("Nightly", bases=["IJob"], line=30),
                          typ("Mail", bases=["IConsumer<OrderPlaced>"], line=60), typ("Nsb", bases=["IHandleMessages<Cmd>"], line=90),
                          typ("Svc", bases=["Microsoft.Extensions.Hosting.IHostedService"], line=120))}

        got = [(r["kind"], r["name"], r["trigger"]) for r in cs_entries.class_entries(d)]

        assert got == [("hosted-service", "Cleanup", "when the host starts"), ("scheduled-job", "Nightly", "a schedule"),
                       ("queue-consumer", "Mail", "a message for the task `Mail`"), ("queue-consumer", "Nsb", "a message for the task `Nsb`"),
                       ("hosted-service", "Svc", "when the host starts")]

    def test_abstract_classes_and_kafka_two_argument_consumers_are_skipped(self):
        d = {"c.cs": file(typ("A", bases=["BackgroundService"], mods=("public", "abstract")), typ("K", bases=["IConsumer<string, int>"]))}

        assert cs_entries.class_entries(d) == []


def fn(name, trigger=None, attr_name="Function", line=7):
    params = [{"name": "req", "type": "string", "this": False, "attrs": [trigger] if trigger else []}]
    return method("Run", [attr(attr_name, f'"{name}"')], params=params, line=line)


class TestFunctionEntries:
    def test_http_trigger_is_a_web_request(self):
        got = cs_entries.function_entries({"f.cs": file(typ("Ping", [fn("Ping", "HttpTrigger")]))})

        assert [(r["kind"], r["name"], r["trigger"], r["line"]) for r in got] == [("function", "Ping", "a web request to `Ping`", 7)]

    def test_timer_trigger_is_a_scheduled_job(self):
        got = cs_entries.function_entries({"f.cs": file(typ("Ping", [fn("Tick", "TimerTrigger")]))})

        assert [(r["kind"], r["trigger"]) for r in got] == [("scheduled-job", "a schedule")]

    def test_queue_and_service_bus_triggers_are_messages(self):
        d = {"f.cs": file(typ("P", [fn("Q", "QueueTrigger", line=1), fn("S", "ServiceBusTrigger", line=2), fn("C", "CosmosDBTrigger", line=3)]))}

        assert {r["trigger"] for r in cs_entries.function_entries(d)} == {"a message or a change for `Q`", "a message or a change for `S`", "a message or a change for `C`"}

    def test_no_known_trigger_says_azure_functions_calls_it(self):
        got = cs_entries.function_entries({"f.cs": file(typ("P", [fn("X")]))})

        assert got[0]["trigger"] == "when Azure Functions calls X"

    def test_function_name_attribute_of_the_older_model_works(self):
        got = cs_entries.function_entries({"f.cs": file(typ("P", [fn("Old", "HttpTrigger", attr_name="FunctionName")]))})

        assert got[0]["name"] == "Old"


class TestPageRoutes:
    def _routes(self, files):
        return [(r["kind"], r["name"], r["line"]) for r in cs_entries.page_routes(sorted(files), files.get)]

    def test_razor_component_page_is_a_ui_route(self):
        assert self._routes({"A/Components/Counter.razor": '@page "/counter"\n<p/>'}) == [("ui-route", "/counter", 1)]

    def test_a_razor_component_with_two_pages_gives_two_rows(self):
        assert [r[1] for r in self._routes({"A/X.razor": '<p/>\n@page "/a"\n@page "/b"'})] == ["/a", "/b"]

    def test_razor_page_with_a_root_route_replaces_the_path(self):
        assert self._routes({"A/Pages/Index.cshtml": '@page "/"\n<h1/>'}) == [("http-route", "GET /", 1)]

    def test_razor_page_with_no_route_uses_its_folder_path(self):
        files = {"A/Pages/Orders/Detail.cshtml": "@page\n", "A/Pages/Index.cshtml": "@page\n", "A/Pages/Orders/Index.cshtml": "@page\n"}

        assert sorted(r[1] for r in self._routes(files)) == ["GET /", "GET /Orders", "GET /Orders/Detail"]

    def test_a_relative_template_is_added_to_the_path(self):
        assert self._routes({"A/Pages/Orders/Detail.cshtml": '@page "{id}"'}) == [("http-route", "GET /Orders/Detail/{id}", 1)]

    def test_files_without_page_and_underscore_files_give_nothing(self):
        assert self._routes({"A/Pages/_Layout.cshtml": "@page", "A/Pages/Partial.cshtml": "<p/>", "A/Views/Home/Index.cshtml": "<h1/>"}) == []
