"""The C# adapter (frame): solutions, projects and the notes Gaps needs, plus the per-tool status for each step.

scip-dotnet is gated on its own (trust and the .NET SDK), so semgrep and tree-sitter never depend on the SDK (plan 011, D1).
Later tasks fill the steps that are recorded as skipped here.
"""
from __future__ import annotations

from pathlib import Path

import candidates
import config
import cs_api
import cs_entries
import cs_graph
import cs_models
import cs_project
import cs_queries
import cs_scip
import cs_sdk
import cs_semgrep
import cs_tests
import scip_read
import toolcheck
from adapters import OUTPUTS, Adapter
from gather import TEST_RE

RULES = Path(__file__).resolve().parent.parent / "rules" / "csharp"
NOT_TRUSTED = "The ref is not trusted, so scip-dotnet did not run. Use --allow-ref to run it."
NO_RUNTIME = "scip-dotnet needs the .NET 8, 9 or 10 runtime, and none is installed."
RAZOR_EXTS = (".razor", ".cshtml")
GENERATOR_PACKAGES = ("Riok.Mapperly", "Mediator.SourceGenerator", "CommunityToolkit.Mvvm", "Refit", "StronglyTypedId", "Vogen")


class CSharpAdapter(Adapter):
    name = "csharp"
    version = "2"
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
                          "frameworks": p["frameworks"], "test": p["test"], "packable": p["packable"], "references": p["references"], "friends": p["friends"]})
            for ref in p["references"]:
                if ref in by_path:
                    items.append({"kind": "project-reference", "path": p["path"], "paths": [ref], "from": p["name"], "to": by_path[ref]["name"]})
        return items + cs_project.source_roots(result, tree)

    @staticmethod
    def _notes(result, tree) -> list:
        notes = []
        for p in (q for q in result["projects"] if "language" not in q):
            for name in cs_project.project_frameworks(p):
                notes.append({"kind": "cs-note", "path": p["path"], "note": "framework", "name": name})
            if not p["lock"]:
                notes.append({"kind": "cs-note", "path": p["path"], "note": "no-lock", "name": p["name"]})
        for p in (q for q in result["projects"] if "language" not in q):
            for name in GENERATOR_PACKAGES:
                if name in p["packages"]:
                    notes.append({"kind": "cs-note", "path": p["path"], "note": "generator", "name": f"{name}|{p['path']}"})
        razor = sorted(f for f in tree if f.endswith(RAZOR_EXTS))
        if razor:
            notes.append({"kind": "cs-note", "path": razor[0], "note": "razor", "name": str(len(razor))})
        return notes

    def _scip_gate(self, ctx, read) -> str | None:
        """The reason scip-dotnet cannot run, or None."""
        if not ctx.trusted:
            return NOT_TRUSTED
        return cs_sdk.problem(cs_sdk.list_sdks(), cs_sdk.requirements(sorted(ctx.tree), read))

    @staticmethod
    def _failed(ctx, tool: str, e: Exception) -> None:
        ctx.tool_status[tool] = {"status": "failed", "reason": (str(e).splitlines() or [type(e).__name__])[0]}

    @staticmethod
    def _test_files(result, files) -> set:
        """Every `.cs` file in a test project, plus the ones whose name says test."""
        in_tests = {f for p in result["projects"] if "language" not in p and p["test"] for f in p["files"]}
        return in_tests | {f for f in files if TEST_RE.search(f)}

    def _syntax(self, ctx, out, result, read, st) -> None:
        """Declarations, the type-use graph and complexity with tree-sitter. Needs no .NET SDK."""
        files = sorted(set(result["loose_files"]) | {f for p in result["projects"] if "language" not in p for f in p["files"]})
        tests = self._test_files(result, files)
        generated = {f for f in files if cs_project.is_generated(f, read)}
        st.update(files=files, tests=tests, generated=generated)
        try:
            decls = cs_queries.declarations(ctx.treesitter, files)
            counts = cs_queries.complexity(ctx.treesitter, [f for f in files if f not in generated and f not in tests])
        except Exception as e:  # one tool failing must not stop the others
            return self._failed(ctx, "tree-sitter-language-pack", e)
        ctx.tool_status["tree-sitter-language-pack"] = {"status": "ok", "reason": None}
        imports, test_edges, ambiguous = cs_graph.type_uses(decls, result, tests, generated)
        out["graph"] += (cs_graph.module_items(result, decls, counts, generated, tests) + imports
                         + cs_graph.namespace_cycles(imports, decls, result))
        if ambiguous:
            out["graph"].append({"kind": "cs-note", "path": files[0], "note": "ambiguous-name", "name": str(ambiguous)})
        api, api_notes, _ = cs_api.items(result["projects"], decls, generated)
        out["symbols"] += api
        out["graph"] += api_notes
        out["models"] += cs_models.model_items(decls, result, read, generated, tests)
        found = cs_tests.tests(decls, result, read, tests)
        edges: dict = {}
        for a, b in test_edges:
            edges.setdefault(a, set()).add(b)
        modules = {g["path"]: g["module"] for g in out["graph"] if g["kind"] == "module"}
        for t in found:
            t["paths"] = sorted(edges.get(t["path"], ()))
            t["imports"] = sorted({modules[p] for p in t["paths"] if p in modules})
        out["tests"] += found + cs_tests.test_configs(sorted(ctx.tree), read, result)
        out["io_candidates"] += cs_tests.module_state(decls, tests | generated)
        st.update(decls=decls, test_edges=test_edges)

    def _semgrep(self, ctx, out, result, st) -> None:
        """Entry points, I/O sites and blind spots with the C# rules, in source files that are not generated."""
        scan = [f for f in st["files"] if f not in st["generated"]]
        if not scan:
            return self._skipped(ctx, "semgrep", "There are no C# files to scan.")
        owner = {f: p["path"] for p in result["projects"] if "language" not in p for f in p["files"]}
        builders = {p["path"] for p in result["projects"] if "language" not in p and {"bullseye", "cake.frosting"} & {x.lower() for x in p["packages"]}}
        try:
            found = cs_semgrep.items(ctx.semgrep.scan(RULES, scan), owner.get, builders, self._reader(ctx))
        except Exception as e:  # one tool failing must not stop the others
            return self._failed(ctx, "semgrep", e)
        ctx.tool_status["semgrep"] = {"status": "ok", "reason": None}
        found["entry_points"] = [e for e in found["entry_points"] if e["path"] not in st["tests"]]
        found["blindspots"] += self._codegen_hits(ctx, st)
        for key, rows in found.items():
            out[key] += rows

    @staticmethod
    def _codegen_hits(ctx, st) -> list:
        """One `codegen` blind spot per generated file. Generated files are not scanned by the rules, so these come from the file header."""
        hits = []
        for path in sorted(st["generated"]):
            try:
                lines = (ctx.checkout / path).read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                lines = []
            line = next((n for n, text in enumerate(lines[:10], 1) if "<auto-generated" in text), 1)
            hits.append({"path": path, "line": line, "end_line": line, "rule": "dossier.csharp.blindspot.codegen",
                         "snippet": (lines[line - 1].strip() if lines else "")[:200], "pattern": "codegen"})
        return hits

    @staticmethod
    def _skipped(ctx, tool: str, reason: str) -> None:
        ctx.tool_status[tool] = {"status": "skipped", "reason": reason}

    @staticmethod
    def _fallback(out, st, why: str, ctx, status: str = "skipped") -> None:
        """scip-dotnet did not give symbols: record why, and list the declarations from tree-sitter instead (D11)."""
        ctx.tool_status["scip-dotnet"] = {"status": status, "reason": why}
        out["symbols"] += cs_scip.fallback_defs(st.get("decls", {}), st.get("generated", set()))

    def _install(self, ctx, timeout):
        """(ScipDotnet client, None) or (None, (status, reason))."""
        tool = next(t for t in toolcheck.load_tools()["tools"] if t["id"] == "scip-dotnet")
        try:
            folder = cs_scip.ensure_installed(ctx.area.parent, tool, timeout)
        except Exception as e:  # a failed download must not stop the other tools
            return None, ("failed", (str(e).splitlines() or [type(e).__name__])[0])
        dll = cs_scip.tool_dll(folder, cs_sdk.list_runtime_majors())
        return (cs_scip.ScipDotnet(ctx.run, dll, timeout), None) if dll else (None, ("skipped", NO_RUNTIME))

    @staticmethod
    def _run_targets(ctx, scip, targets) -> tuple:
        """(decoded indexes, problems, msbuild notes). One failing target does not stop the others."""
        indexes, problems, notes = [], [], []
        for n, target in enumerate(targets):
            try:
                path, code, log = scip.index(ctx.checkout, target, ctx.area, n)
                bad = cs_scip.failure(code, log, path)
                if bad:
                    problems.append(bad)
                    continue
                indexes.append(scip_read.decode(path.read_bytes()))
            except Exception as e:  # a bad index must not stop the other targets
                problems.append((str(e).splitlines() or [type(e).__name__])[0])
                continue
            soft = cs_scip.soft_failure(log)
            if soft:
                problems.append(f"scip-dotnet could not load every project: {soft}")
                notes.append({"kind": "cs-note", "path": target, "note": "msbuild", "name": soft})
        return indexes, problems, notes

    def _scip(self, ctx, out, result, st, gate) -> None:
        """Symbols and references with scip-dotnet, or the tree-sitter fallback when it could not run or gave nothing (D11)."""
        if gate:
            where = (result["targets"] or [p["path"] for p in result["projects"] if "language" not in p] or st.get("files") or [None])[0]
            if gate != NOT_TRUSTED and where:
                out["graph"].append({"kind": "cs-note", "path": where, "note": "sdk", "name": gate})
            return self._fallback(out, st, gate, ctx)
        scip, problem = self._install(ctx, config.timeouts()["tool"])
        if problem:
            return self._fallback(out, st, problem[1], ctx, problem[0])
        indexes, problems, notes = self._run_targets(ctx, scip, result["targets"])
        out["graph"] += notes
        index = cs_scip.join(indexes, ctx.tree)
        if not index["documents"]:
            return self._fallback(out, st, problems[0] if problems else "scip-dotnet wrote an index with no documents.", ctx, "failed")
        decls = st.get("decls", {})
        index, ambiguous = cs_scip.disambiguate(index, decls)
        symbols = cs_scip.finish_symbols(scip_read.reduce(index), decls, st.get("generated", set()))
        csprojects = [p for p in result["projects"] if "language" not in p]
        symbols, dropped = cs_scip.drop_unrelated(symbols, csprojects, {f: p["path"] for p in csprojects for f in p["files"]})
        out["symbols"] += symbols
        ctx.details["dropped_edges"] = dropped
        indexed = {d["path"] for d in index["documents"]}
        missing = sorted(f for p in result["projects"] if "language" not in p for f in p["files"] if f not in indexed and f not in st.get("generated", ()))
        for note, count, path in (("ambiguous-symbol", ambiguous, result["targets"][0]), ("unindexed", len(missing), missing[0] if missing else None)):
            if count:
                out["graph"].append({"kind": "cs-note", "path": path, "note": note, "name": str(count)})
        if problems:
            ctx.tool_status["scip-dotnet"] = {"status": "failed", "reason": problems[0]}
            return
        ctx.tool_status["scip-dotnet"] = {"status": "ok", "reason": None}
        dead = cs_scip.dead_items(out["symbols"], decls, out["entry_points"], out["models"], out["blindspots"], st.get("generated", set()), st.get("tests", set()))
        out["dead"] += dead
        if dead:
            out["graph"].append({"kind": "cs-note", "path": dead[0]["path"], "note": "dead", "name": str(len(dead))})

    def extract(self, ctx) -> dict:
        out = {o: [] for o in OUTPUTS}
        read = self._reader(ctx)
        result = cs_project.projects(sorted(ctx.tree), read)
        out["graph"] += self._project_items(result, ctx.tree) + self._notes(result, ctx.tree)
        st: dict = {}
        self._syntax(ctx, out, result, read, st)
        self._semgrep(ctx, out, result, st)
        out["io_candidates"] += cs_semgrep.config_inputs(sorted(ctx.tree), read)
        out["entry_points"] += cs_entries.page_routes(sorted(ctx.tree), read)
        if "decls" in st:
            decls = {f: d for f, d in st["decls"].items() if f not in st["generated"]}
            out["entry_points"] += (cs_entries.controller_routes(decls) + cs_entries.program_entries(result, decls)
                                    + cs_entries.class_entries(decls) + cs_entries.function_entries(decls))
        self._scip(ctx, out, result, st, self._scip_gate(ctx, read))
        return {o: candidates.sort_items(items) for o, items in out.items()}
