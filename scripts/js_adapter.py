"""The JavaScript and TypeScript adapter (frame): entry points from project files, and the per-tool status for each step.

The Node steps (TypeScript script, dependency-cruiser, knip, scip-typescript) are built; tree-sitter and semgrep arrive in later tasks
and record `skipped` until then. The four Node tools are gated one by one, so semgrep and tree-sitter never depend on Node.
"""
from __future__ import annotations

import json
from pathlib import Path

import candidates
import config
import js_entries
import js_prisma
import js_project
import js_queries
import js_reduce
import js_tools
import scip_read
from adapters import OUTPUTS, Adapter
from gather import TEST_RE

NODE_TOOLS = ("dependency-cruiser", "knip", "scip-typescript", "typescript")
CRUISE_CONFIGS = tuple(f".dependency-cruiser.{e}" for e in ("js", "cjs", "mjs", "ts", "cts", "mts", "json"))
LATER = "Arrives in a later task."


class JsAdapter(Adapter):
    name = "js"
    version = "1"
    languages = ("JavaScript", "TypeScript")
    tools = ("dependency-cruiser", "knip", "scip-typescript", "typescript", "semgrep", "tree-sitter-language-pack")
    expected_untracked = ("**/node_modules/**",)
    loads_repo_code = False

    @staticmethod
    def _skip(ctx, tool: str, reason: str) -> None:
        ctx.tool_status[tool] = {"status": "skipped", "reason": reason}

    def _node_gate(self, ctx) -> str | None:
        """The reason the Node tools cannot run, or None."""
        if not ctx.trusted:
            return js_tools.NOT_TRUSTED
        try:
            return js_tools.node_problem(ctx.run)
        except Exception as e:  # a failed check must not stop the steps that need no Node
            return (str(e).splitlines() or [type(e).__name__])[0]

    @staticmethod
    def _reader(ctx):
        def read(path):
            try:
                return (ctx.checkout / path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                return None
        return read

    def _entries(self, ctx, out, projects, read) -> None:
        tracked = sorted(ctx.tree)
        for project in projects:
            out["entry_points"] += js_entries.package_entries(project, read)
            for folder in project["members"]:
                manifest = js_project.read_json(read, f"{folder}/package.json" if folder else "package.json") or {}
                deps = {**(manifest.get("devDependencies") or {}), **(manifest.get("dependencies") or {})}
                if "next" in deps:
                    out["entry_points"] += js_entries.next_routes(tracked, {"dir": folder})
        out["entry_points"] += js_entries.nx_targets(ctx.tree, read)

    @staticmethod
    def _each(ctx, tool: str, projects: list, fn) -> dict:
        """Run `fn(project)` for each project. One failing project marks the tool failed (naming it) and the others still run."""
        results, failed = {}, None
        for p in projects:
            try:
                results[p["dir"]] = fn(p)
            except Exception as e:  # one project failing must not stop the others
                failed = failed or f"{p['dir'] or 'the repository root'}: {(str(e).splitlines() or [type(e).__name__])[0]}"
        ctx.tool_status[tool] = {"status": "failed", "reason": failed} if failed else {"status": "ok", "reason": None}
        return results

    def _facts(self, ctx, install, projects, timeout) -> dict:
        client = js_tools.TsFacts(ctx.run, install, timeout)

        def one(p):
            folder = p["dir"]
            names = [f[len(folder) + 1:] if folder else f for f in p["files"]]
            return js_reduce.prefix_facts(client.facts(ctx.checkout / folder, names), folder)
        return self._each(ctx, "typescript", projects, one)

    def _graph(self, ctx, out, install, projects, facts, timeout) -> list:
        """Adds module, import, cycle and contract items to `out`. Returns the (from, to) edges that start in test files, for the tests step."""
        cruiser = js_tools.DepCruiser(ctx.run, install, timeout)
        tree = frozenset(ctx.tree)

        def one(p):
            folder = p["dir"]
            used = ((facts.get(folder) or {}).get("config") or {}).get("used")
            cruise = cruiser.cruise(ctx.checkout / folder, used)
            imports = (facts.get(folder) or {}).get("imports", [])
            items, test_edges = js_reduce.graph_items(cruise, p, tree, imports, TEST_RE)
            names = {i["path"]: i["module"] for i in items if i["kind"] == "module"}
            return items + self._contracts(ctx, cruiser, p, names, items), test_edges
        got = self._each(ctx, "dependency-cruiser", projects, one)
        edges = []
        for items, test_edges in got.values():
            out["graph"] += items
            edges += test_edges
        return edges

    def _syntax(self, ctx, out, st, projects) -> None:
        """Tests, complexity and module-level state with tree-sitter. Needs no Node."""
        files = sorted({f for p in projects for f in p["files"]})
        test_files = [f for f in files if TEST_RE.search(f)]
        src = [f for f in files if f not in set(test_files) and not f.endswith(".d.ts")]
        configs = js_queries.test_configs(sorted(ctx.tree), st["read"])
        runner = js_queries.runner_of(configs)

        def go():
            return js_queries.tests(ctx.treesitter, test_files, runner), js_queries.complexity(ctx.treesitter, src), js_queries.module_state(ctx.treesitter, src)
        try:
            found = go()
        except Exception as e:  # one tool failing must not stop the others
            ctx.tool_status["tree-sitter-language-pack"] = {"status": "failed", "reason": (str(e).splitlines() or [type(e).__name__])[0]}
            return
        ctx.tool_status["tree-sitter-language-pack"] = {"status": "ok", "reason": None}
        tests, counts, state = found
        names = {g["path"]: g["module"] for g in out["graph"] if g["kind"] == "module"}
        edges: dict = {}
        for a, b in st["test_edges"]:
            edges.setdefault(a, set()).add(b)
        for t in tests:
            t["paths"] = sorted(edges.get(t["path"], ()))
            t["imports"] = sorted({names[p] for p in t["paths"] if p in names})
        for g in out["graph"]:
            if g["kind"] == "module":
                g["complexity"] = counts.get(g["path"], 0)
        out["tests"] += tests + configs
        out["io_candidates"] += state

    @staticmethod
    def _prisma(ctx, out, read) -> None:
        """Prisma schemas need no tool, so they are read even when Node is missing."""
        for path in sorted(p for p in ctx.tree if p.endswith(".prisma")):
            text = read(path)
            if text is not None:
                parsed = js_prisma.parse(path, text)
                out["models"] += parsed["models"]
                out["io_candidates"] += parsed["io"]

    def _dead(self, ctx, out, install, projects, timeout) -> None:
        knip = js_tools.Knip(ctx.run, install, timeout)
        got = self._each(ctx, "knip", projects, lambda p: js_reduce.dead_items(knip.run_knip(ctx.checkout / p["dir"]), p))
        for items in got.values():
            out["dead"] += items

    def _symbols(self, ctx, out, install, projects, facts, timeout) -> None:
        scip = js_tools.ScipTs(ctx.run, install, timeout)
        numbers = {p["dir"]: n for n, p in enumerate(projects)}

        def one(p):
            has_ts = (f"{p['dir']}/tsconfig.json" if p["dir"] else "tsconfig.json") in ctx.tree
            index = scip.index(ctx.checkout / p["dir"], ctx.area, numbers[p["dir"]], has_ts)
            return p["dir"], scip_read.decode(index.read_bytes())
        got = self._each(ctx, "scip-typescript", projects, one)
        if not got:
            return
        items = scip_read.reduce(js_reduce.join_indexes(list(got.values())))
        ok = ctx.tool_status.get("typescript", {}).get("status") == "ok"
        exports = [e for f in facts.values() for e in f.get("exports", [])] if ok else None
        out["symbols"] += js_reduce.finish_symbols(items, exports)

    @staticmethod
    def _contracts(ctx, cruiser, project, names, items) -> list:
        folder = project["dir"]
        config_file = next((c for c in CRUISE_CONFIGS if (f"{folder}/{c}" if folder else c) in ctx.tree), None)
        if config_file is None:
            return []
        full = f"{folder}/{config_file}" if folder else config_file
        found = cruiser.violations(ctx.checkout / folder, config_file)
        found = [{**v, "from": f"{folder}/{v['from']}" if folder else v["from"], "to": f"{folder}/{v['to']}" if folder else v["to"]} for v in found]
        declared = []
        if config_file.endswith(".json"):
            try:
                declared = [r["name"] for r in json.loads((ctx.checkout / full).read_text()).get("forbidden", []) if "name" in r]
            except (OSError, ValueError, AttributeError):
                declared = []
        lines = {(i["path"], i["paths"][0]): (i["lines"] or [None])[0] for i in items if i["kind"] == "import"}
        return js_reduce.contract_items(found, declared, full, names, lines)

    def extract(self, ctx) -> dict:
        out = {o: [] for o in OUTPUTS}
        read = self._reader(ctx)
        projects = js_project.projects(sorted(ctx.tree), read)
        self._entries(ctx, out, projects, read)
        self._prisma(ctx, out, read)
        st = {"test_edges": [], "read": read}
        gate = self._node_gate(ctx)
        self._skip(ctx, "semgrep", LATER)
        if gate:
            self._skip(ctx, "typescript", gate)
            self._skip(ctx, "dependency-cruiser", gate)
            self._skip(ctx, "knip", gate)
            self._skip(ctx, "scip-typescript", gate)
        else:
            timeout = config.timeouts()["tool"]
            try:
                install = js_tools.ensure_installed(ctx.run, ctx.area.parent, timeout)
            except Exception as e:
                reason = (str(e).splitlines() or [type(e).__name__])[0]
                for tool in NODE_TOOLS:
                    ctx.tool_status[tool] = {"status": "failed", "reason": reason}
            else:
                facts = self._facts(ctx, install, projects, timeout)
                st["test_edges"] = self._graph(ctx, out, install, projects, facts, timeout)
                self._dead(ctx, out, install, projects, timeout)
                out["models"] += js_reduce.model_items([t for f in facts.values() for t in f.get("types", [])])
                self._symbols(ctx, out, install, projects, facts, timeout)
        self._syntax(ctx, out, st, projects)
        return {o: candidates.sort_items(items) for o, items in out.items()}
