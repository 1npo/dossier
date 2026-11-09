"""C# entry points that can be read from declarations and project files (plan 011, D9). Pure.

Controllers, `Main` and top-level statements, hosted services, Quartz jobs, message consumers, Azure Functions, and the `@page`
routes of Razor Pages and Blazor. Minimal APIs, SignalR, gRPC and the other call-shaped entries come from the semgrep rules.
"""
from __future__ import annotations

import re

import cs_queries

VERBS = {"HttpGet": "GET", "HttpPost": "POST", "HttpPut": "PUT", "HttpPatch": "PATCH", "HttpDelete": "DELETE", "HttpHead": "HEAD", "HttpOptions": "OPTIONS"}
FUNCTION_TRIGGERS = {"HttpTrigger": "a web request to `{name}`", "TimerTrigger": "a schedule",
                     "QueueTrigger": "a message or a change for `{name}`", "ServiceBusTrigger": "a message or a change for `{name}`",
                     "EventHubTrigger": "a message or a change for `{name}`", "BlobTrigger": "a message or a change for `{name}`",
                     "CosmosDBTrigger": "a message or a change for `{name}`"}
PAGE_RE = re.compile(r'^@page(?:[ \t]+"([^"]*)")?', re.M)


def _item(path, line, kind, name, trigger, rule, snippet=None):
    return {"path": path, "line": line, "end_line": line, "kind": kind, "name": name, "trigger": trigger, "target": path, "rule": rule,
            "snippet": snippet or name}


def _first_string(attr: dict) -> str | None:
    """The route template an attribute gives: its first argument when that is a string literal (not `Name = "x"`)."""
    args = attr["args"].lstrip()
    if not args.startswith('"'):
        return None
    found = cs_queries.strings_in(args)
    return found[0] if found else None


def _attr(attrs: list, *names) -> list:
    return [a for a in attrs if a["name"] in names]


def _is_controller(t: dict) -> bool:
    if "abstract" in t["modifiers"] or t["kind"] != "class" or _attr(t["attributes"], "NonController"):
        return False
    bases = {re.sub(r"<.*$", "", b).rsplit(".", 1)[-1] for b in t["bases"]}
    return t["name"].endswith("Controller") or bool(bases & {"Controller", "ControllerBase"}) or bool(_attr(t["attributes"], "ApiController", "Controller"))


def _path(prefix: str, template: str, controller: str, action: str) -> str:
    if template.startswith(("/", "~/")):
        joined = template.lstrip("~").strip("/")
    else:
        joined = "/".join(p.strip("/") for p in (prefix, template) if p.strip("/"))
    joined = joined.replace("[controller]", controller).replace("[action]", action)
    return "/" + joined


def controller_routes(decls: dict) -> list:
    """`http-route` rows for the attribute routes of every controller."""
    out = []
    for path, d in sorted(decls.items()):
        for t in d["types"]:
            if not _is_controller(t):
                continue
            route = _attr(t["attributes"], "Route")
            prefix = (_first_string(route[0]) or "") if route else ""
            controller = t["name"][:-10] if t["name"].endswith("Controller") else t["name"]
            for m in t["members"]:
                if m["kind"] != "method" or "public" not in m["modifiers"] or m["static"]:
                    continue
                routes = _attr(m["attributes"], "Route")
                tpl_route = (_first_string(routes[0]) or "") if routes else ""
                rows = []
                for a in _attr(m["attributes"], *VERBS):
                    rows.append((VERBS[a["name"]], _first_string(a) if _first_string(a) is not None else tpl_route))
                for a in _attr(m["attributes"], "AcceptVerbs"):
                    rows += [(v.upper(), tpl_route) for v in cs_queries.strings_in(a["args"])]
                if not rows and routes:
                    rows = [("ANY", tpl_route)]
                for verb, template in rows:
                    if not prefix and not template:
                        continue  # no attribute route at all: reached through a route template, which the blind spot covers
                    name = f"{verb} {_path(prefix, template, controller, m['name'])}"
                    out.append(_item(path, m["line"], "http-route", name, f"a web request to `{name}`", "cs.controller-route", name))
    return out


def program_entries(projects: dict, decls: dict) -> list:
    """`program-main` rows: a static `Main`, or top-level statements, in a project that is not a test project."""
    out = []
    for p in projects["projects"]:
        if "language" in p or p["test"]:
            continue
        for f in p["files"]:
            d = decls.get(f)
            if not d:
                continue
            mains = [m for t in d["types"] for m in t["members"] if m["kind"] == "method" and m["name"] == "Main" and m["static"]]
            line = mains[0]["line"] if mains else d.get("top_level_line") or 1 if d["top_level"] else None
            if line:
                out.append(_item(f, line, "program-main", p["name"], f"starting `{p['name']}` (for example with `dotnet run`)", "cs.program-main", p["name"]))
    return out


def _base_names(t: dict) -> list:
    return [b.rsplit(".", 1)[-1] for b in t["bases"]]


def class_entries(decls: dict) -> list:
    """Hosted services, Quartz jobs and message consumers, from the base list of a class that is not abstract."""
    out = []
    for path, d in sorted(decls.items()):
        for t in d["types"]:
            if t["kind"] != "class" or "abstract" in t["modifiers"]:
                continue
            bases = _base_names(t)
            name = t["name"]
            if any(b in ("BackgroundService", "IHostedService") for b in bases):
                out.append(_item(path, t["line"], "hosted-service", name, "when the host starts", "cs.hosted-service"))
            if any(b == "IJob" for b in bases):
                out.append(_item(path, t["line"], "scheduled-job", name, "a schedule", "cs.quartz-job"))
            if any(re.match(r"(IConsumer|IHandleMessages)<[^,]*>$", b) for b in bases):
                out.append(_item(path, t["line"], "queue-consumer", name, f"a message for the task `{name}`", "cs.consumer"))
    return out


def function_entries(decls: dict) -> list:
    """Azure Functions: `[Function("N")]` and `[FunctionName("N")]`. A timer trigger is a `scheduled-job`."""
    out = []
    for path, d in sorted(decls.items()):
        for t in d["types"]:
            for m in t["members"]:
                marks = _attr(m["attributes"], "Function", "FunctionName")
                if m["kind"] != "method" or not marks:
                    continue
                name = _first_string(marks[0]) or m["name"]
                triggers = [a for p in m["params"] for a in p.get("attrs", []) if a in FUNCTION_TRIGGERS]
                trigger = triggers[0] if triggers else None
                if trigger == "TimerTrigger":
                    out.append(_item(path, m["line"], "scheduled-job", name, "a schedule", "cs.function"))
                else:
                    text = FUNCTION_TRIGGERS[trigger].format(name=name) if trigger else f"when Azure Functions calls {name}"
                    out.append(_item(path, m["line"], "function", name, text, "cs.function"))
    return out


def _pages_route(path: str) -> str:
    rest = path.split("/Pages/", 1)[1] if "/Pages/" in path else path
    rest = rest[:-len(".cshtml")]
    if rest.endswith("Index"):
        rest = rest[:-5].rstrip("/")
    return "/" + rest.strip("/")


def page_routes(tree, read) -> list:
    """`@page` routes: `ui-route` for Blazor `.razor` files, `http-route` for Razor Pages `.cshtml` files."""
    out = []
    for path in sorted(tree):
        if not path.endswith((".razor", ".cshtml")) or path.rsplit("/", 1)[-1].startswith("_"):
            continue
        text = read(path) or ""
        for found in PAGE_RE.finditer(text):
            line = text.count("\n", 0, found.start()) + 1
            route = found.group(1)
            if path.endswith(".razor"):
                if route is None:
                    continue
                out.append(_item(path, line, "ui-route", route, f"opening `{route}` in the browser", "cs.razor-page"))
                continue
            base = _pages_route(path)
            full = route if route and route.startswith("/") else "/".join(p.strip("/") for p in (base, route or "") if p.strip("/"))
            full = full if full.startswith("/") else "/" + full
            out.append(_item(path, line, "http-route", f"GET {full}", f"a web request to `GET {full}`", "cs.razor-page"))
    return out
