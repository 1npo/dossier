"""The JavaScript and TypeScript adapter (frame): entry points from project files, and the per-tool status for each step.

The tool steps (tree-sitter, semgrep, dependency-cruiser, knip, scip-typescript and the TypeScript script) arrive in later tasks;
until then each records `skipped`. The four Node tools are gated one by one, so semgrep and tree-sitter never depend on Node.
"""
from __future__ import annotations

import candidates
import js_entries
import js_project
import js_tools
from adapters import OUTPUTS, Adapter

NODE_TOOLS = ("dependency-cruiser", "knip", "scip-typescript", "typescript")
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

    def extract(self, ctx) -> dict:
        out = {o: [] for o in OUTPUTS}
        read = self._reader(ctx)
        self._entries(ctx, out, js_project.projects(sorted(ctx.tree), read), read)
        gate = self._node_gate(ctx)
        for tool in NODE_TOOLS:
            self._skip(ctx, tool, gate or LATER)
        for tool in ("semgrep", "tree-sitter-language-pack"):
            self._skip(ctx, tool, LATER)
        return {o: candidates.sort_items(items) for o, items in out.items()}
