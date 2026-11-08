"""The C# adapter (frame): solutions, projects and the notes Gaps needs, plus the per-tool status for each step.

scip-dotnet is gated on its own (trust and the .NET SDK), so semgrep and tree-sitter never depend on the SDK (plan 011, D1).
Later tasks fill the steps that are recorded as skipped here.
"""
from __future__ import annotations

from pathlib import Path

import cs_project
import cs_sdk
from adapters import OUTPUTS, Adapter

RULES = Path(__file__).resolve().parent.parent / "rules" / "csharp"
NOT_TRUSTED = "The ref is not trusted, so scip-dotnet did not run. Use --allow-ref to run it."
LATER = "Arrives in a later task."
RAZOR_EXTS = (".razor", ".cshtml")


class CSharpAdapter(Adapter):
    name = "csharp"
    version = "1"
    rules = (RULES,)
    languages = ("C#",)
    tools = ("scip-dotnet", "semgrep", "tree-sitter-language-pack")
    expected_untracked = ("**/bin/**", "**/obj/**", "artifacts/**")
    loads_repo_code = False

    @staticmethod
    def _reader(ctx):
        def read(path):
            try:
                return (ctx.checkout / path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                return None
        return read

    @staticmethod
    def _project_items(result, tree) -> list:
        cs = [p for p in result["projects"] if "language" not in p]
        by_path = {p["path"]: p for p in cs}
        items = []
        for p in cs:
            items.append({"kind": "cs-project", "path": p["path"], "name": p["name"], "sdk": p["sdk"], "output_type": p["output_type"],
                          "frameworks": p["frameworks"], "test": p["test"], "packable": p["packable"], "references": p["references"]})
            for ref in p["references"]:
                if ref in by_path:
                    items.append({"kind": "project-reference", "path": p["path"], "paths": [ref], "from": p["name"], "to": by_path[ref]["name"]})
        return items + cs_project.source_roots(result, tree)

    @staticmethod
    def _notes(result, tree) -> list:
        notes = []
        for p in (q for q in result["projects"] if "language" not in q):
            for name in cs_project.UNSUPPORTED_FRAMEWORKS:
                if name in p["packages"]:
                    notes.append({"kind": "cs-note", "path": p["path"], "note": "framework", "name": name})
            if not p["lock"]:
                notes.append({"kind": "cs-note", "path": p["path"], "note": "no-lock", "name": p["name"]})
        razor = sorted(f for f in tree if f.endswith(RAZOR_EXTS))
        if razor:
            notes.append({"kind": "cs-note", "path": razor[0], "note": "razor", "name": str(len(razor))})
        return notes

    def _scip_gate(self, ctx, read) -> str | None:
        """The reason scip-dotnet cannot run, or None."""
        if not ctx.trusted:
            return NOT_TRUSTED
        return cs_sdk.problem(cs_sdk.list_sdks(), cs_sdk.requirements(sorted(ctx.tree), read))

    def extract(self, ctx) -> dict:
        out = {o: [] for o in OUTPUTS}
        read = self._reader(ctx)
        result = cs_project.projects(sorted(ctx.tree), read)
        out["graph"] += self._project_items(result, ctx.tree) + self._notes(result, ctx.tree)
        gate = self._scip_gate(ctx, read)
        for tool in self.tools:
            reason = gate if tool == "scip-dotnet" and gate else LATER
            ctx.tool_status[tool] = {"status": "skipped", "reason": reason}
        return out
