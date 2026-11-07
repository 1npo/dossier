"""The JavaScript and TypeScript adapter (frame): entry points from project files, and the per-tool status for each step.

The tool steps (tree-sitter, semgrep, dependency-cruiser, knip, scip-typescript and the TypeScript script) arrive in later tasks;
until then each records `skipped`. The four Node tools are gated one by one, so semgrep and tree-sitter never depend on Node.
"""
from __future__ import annotations

import json
from pathlib import Path

import candidates
import config
import js_entries
import js_project
import js_reduce
import js_tools
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
        st = {"test_edges": []}
        gate = self._node_gate(ctx)
        for tool in ("knip", "scip-typescript", "semgrep", "tree-sitter-language-pack"):
            self._skip(ctx, tool, gate if tool in NODE_TOOLS and gate else LATER)
        if gate:
            self._skip(ctx, "typescript", gate)
            self._skip(ctx, "dependency-cruiser", gate)
        else:
            timeout = config.timeouts()["tool"]
            try:
                install = js_tools.ensure_installed(ctx.run, ctx.area.parent, timeout)
            except Exception as e:
                reason = (str(e).splitlines() or [type(e).__name__])[0]
                for tool in ("typescript", "dependency-cruiser", "knip", "scip-typescript"):
                    ctx.tool_status[tool] = {"status": "failed", "reason": reason}
            else:
                facts = self._facts(ctx, install, projects, timeout)
                st["test_edges"] = self._graph(ctx, out, install, projects, facts, timeout)
        return {o: candidates.sort_items(items) for o, items in out.items()}
