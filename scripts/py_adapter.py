"""The Python adapter: all eight outputs from grimp, vulture, scip-python, tree-sitter and semgrep.

Each tool runs in its own step and records its status in `ctx.tool_status`, so one failing tool never loses the others.
"""
from __future__ import annotations

import ast
import copy
import fnmatch
import os
import re
import shutil
from pathlib import Path, PurePosixPath

import candidates
import config
import gather
import graphs
import py_packages
import py_project
import py_queries
import sandbox
import scip_read
import scip_tool
import toolcheck
from adapters import OUTPUTS, Adapter
from py_tools import Grimp, Vulture

RULES = Path(__file__).resolve().parent.parent / "rules" / "python"
NO_PACKAGE = "No Python package was found, so imports were read from the files directly."
NOT_TRUSTED = "The ref is not trusted, so Node tools did not run. Use --allow-ref to run them."
NO_NODE = "Node is not installed."
CALL_COMMAND_RULES = {"dossier.python.entry.argparse-subcommand", "dossier.python.entry.cli-helper-command"}
HANDLER_ARG = re.compile(r"""\(\s*[rf]?["'][^"']*["']\s*,\s*([A-Za-z_]\w*)""")
TRIGGERS = {"console-script": "the `{name}` command", "main-module": "running `python -m {name}`",
            "main-guard": "running `{name}` as a script", "cli-command": "the `{name}` command",
            "http-route": "a web request to `{name}`", "queue-consumer": "a message for the task `{name}`",
            "scheduled-job": "a schedule"}


def module_name(path: str, roots=(), base: str = "") -> str:
    """Dotted module name of a file. A package root such as `src` is not part of the name, nor is a project folder `base`."""
    for r in roots:
        prefix = r["root"] + "/" if r["root"] else ""
        if path.startswith(prefix + r["package"] + "/"):
            path = path[len(prefix):]
            break
    else:
        if base and path.startswith(base + "/"):
            path = path[len(base) + 1:]
    mod = path[:-3].replace("/", ".") if path.endswith(".py") else path.replace("/", ".")
    return mod[: -len(".__init__")] if mod.endswith(".__init__") else mod


class PythonAdapter(Adapter):
    name = "python"
    rules = (RULES,)
    version = "3"
    languages = ("Python",)
    tools = ("grimp", "vulture", "scip-python", "semgrep", "tree-sitter-language-pack")
    expected_untracked = (".venv/**",)

    # ------------------------------------------------------------ helpers

    @staticmethod
    def _step(ctx, tool: str, fn):
        try:
            result = fn()
        except Exception as e:  # one tool failing must not stop the others
            ctx.tool_status[tool] = {"status": "failed", "reason": (str(e).splitlines() or [type(e).__name__])[0]}
            return None
        ctx.tool_status[tool] = {"status": "ok", "reason": None}
        return result

    @staticmethod
    def _skip(ctx, tool: str, reason: str) -> None:
        ctx.tool_status[tool] = {"status": "skipped", "reason": reason}

    @staticmethod
    def _rel(ctx, path):
        try:
            return PurePosixPath(Path(path).relative_to(ctx.checkout)).as_posix() if path else None
        except ValueError:
            return None

    # ------------------------------------------------------------ steps

    def _graph(self, ctx, out, st, timeout):
        if not st["roots"]:
            return self._skip(ctx, "grimp", NO_PACKAGE)
        roots = sorted({str(ctx.checkout / r["root"]) for r in st["roots"]})
        res = self._step(ctx, "grimp", lambda: Grimp(ctx.run, timeout).graph(roots, sorted({r["package"] for r in st["roots"]}),
                                                                        st["contracts"]["contracts"]))
        if res is None:
            return
        for m in res["modules"]:
            path = self._rel(ctx, m["path"])
            if path:
                st["module_paths"][m["module"]] = path
                out["graph"].append({"kind": "module", "path": path, "module": m["module"], "package": m["module"].split(".")[0],
                                     "is_package": m["is_package"]})
        pairs = []
        for i in res["imports"]:
            a, b = st["module_paths"].get(i["from"]), st["module_paths"].get(i["to"])
            if a and b:
                pairs.append((i["from"], i["to"]))
                out["graph"].append({"kind": "import", "path": a, "paths": [b], "from": i["from"], "to": i["to"], "lines": i["lines"],
                                     "via": "grimp"})
        for members in graphs.cycles(pairs):
            files = [st["module_paths"][m] for m in members]
            out["graph"].append({"kind": "cycle", "path": files[0], "paths": files, "modules": members})
        for spec, c in zip(st["contracts"]["contracts"], res["contracts"]):
            out["graph"].append({"kind": "contract", "path": spec["path"], "contract": c["name"], "type": c["type"], "status": c["status"],
                                 "violations": [{"from": v["from"], "to": v["to"], "path": st["module_paths"].get(v["from"]), "line": v["line"]}
                                                for v in c["violations"]], "reason": c["reason"]})

    def _syntax(self, ctx, out, st):
        loose = st["loose"]
        for p in loose:
            mod = module_name(p, base=st["folder"])
            st["module_paths"].setdefault(mod, p)
            out["graph"].append({"kind": "module", "path": p, "module": mod, "package": None, "is_package": p.endswith("/__init__.py")})

        def go():
            return (py_queries.imports(ctx.treesitter, loose, st["module_paths"]), py_queries.models(ctx.treesitter, st["src"]),
                    py_queries.tests(ctx.treesitter, st["tests"], st["module_paths"]), py_queries.module_state(ctx.treesitter, st["src"]),
                    py_queries.complexity(ctx.treesitter, st["src"]))
        got = self._step(ctx, "tree-sitter-language-pack", go)
        if got:
            out["graph"] += got[0]
            out["models"] += got[1]
            out["tests"] += got[2]
            out["io_candidates"] += got[3]
            for item in out["graph"]:
                if item.get("kind") == "module" and item["path"] in got[4]:
                    item["complexity"] = got[4][item["path"]]

    def _function_after(self, ctx, st, path, line):
        if path not in st["source"]:
            try:
                st["source"][path] = (ctx.checkout / path).read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                st["source"][path] = []
        for text in st["source"][path][line - 1:line + 30]:
            s = text.strip()
            if s.startswith("def ") or s.startswith("async def "):
                return s.split("def ", 1)[1].split("(")[0].strip()
        return None

    def _semgrep(self, ctx, out, st):
        if not st["files"]:
            return self._skip(ctx, "semgrep", "There are no Python files to scan.")
        for r in self._step(ctx, "semgrep", lambda: ctx.semgrep.scan(RULES, list(st["files"]))) or []:
            meta, family = r["metadata"], r["rule"].split(".")[2]
            base = {"path": r["path"], "line": r["start_line"], "end_line": r["end_line"], "rule": r["rule"], "snippet": r["snippet"]}
            if family == "blindspot":
                out["blindspots"].append({**base, "pattern": meta.get("pattern")})
            elif family == "entry":
                kind = meta["kind"]
                name = r.get("detail") or ("__main__" if kind == "main-guard" else r["snippet"])
                called = r["rule"] in CALL_COMMAND_RULES  # registered by a call, not by a decorator on the handler
                func = self._function_after(ctx, st, r["path"], r["start_line"]) if kind in ("cli-command", "http-route", "queue-consumer") and not called else None
                handler = HANDLER_ARG.search(r["snippet"]) if r["rule"].endswith("cli-helper-command") else None
                mod = st["path_module"].get(r["path"]) or module_name(r["path"], st["roots"], st["folder"])
                shown = r["path"] if kind == "main-guard" else name
                target = f"{mod}:{func}" if func else f"{mod}:{handler.group(1)}" if handler else r["path"]
                out["entry_points"].append({**base, "kind": kind, "name": name, "trigger": TRIGGERS[kind].format(name=shown), "target": target})
            else:
                out["io_candidates"].append({**base, "category": meta["category"], "detail": r.get("detail")})

    def _entries(self, ctx, out, st):
        for s in py_packages.console_scripts(st["view"]):
            out["entry_points"].append({"path": self._lift(st, s["path"]), "line": s["line"], "end_line": s["line"], "kind": "console-script",
                                        "name": s["name"], "trigger": TRIGGERS["console-script"].format(name=s["name"]),
                                        "target": s["target"], "rule": "python.console-script",
                                        "snippet": f"{s['name']} = {s['target']}"})
        for p in sorted(x for x in st["files"] if x.endswith("/__main__.py") and not gather.noise_reason(x) and not gather.TEST_RE.search(x)):
            mod = st["path_module"].get(p) or module_name(p, st["roots"], st["folder"])
            pkg = mod[: -len(".__main__")]
            line = 1
            try:
                tree = ast.parse((ctx.checkout / p).read_text(encoding="utf-8"))
                body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))
                        and not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
                line = body[0].lineno if body else 1
            except (OSError, SyntaxError, UnicodeDecodeError):
                pass
            out["entry_points"].append({"path": p, "line": line, "end_line": line, "kind": "main-module", "name": pkg,
                                        "trigger": TRIGGERS["main-module"].format(name=pkg), "target": mod, "rule": "python.main-module",
                                        "snippet": f"python -m {pkg}"})

    def _dead(self, ctx, out, st, timeout):
        cfg = st["vulture"]
        paths = [p for p in st["src"] if not any(fnmatch.fnmatch(self._local(st, p), g) for g in cfg["exclude"])]
        if not paths:
            return self._skip(ctx, "vulture", "There are no Python files to check.")
        for i in self._step(ctx, "vulture", lambda: Vulture(ctx.run, timeout).dead(paths, cfg)) or []:
            out["dead"].append({**i, "rule": "vulture." + i["type"], "snippet": i["name"]})

    def _symbols(self, ctx, out, st, timeout):
        if not ctx.trusted:
            return self._skip(ctx, "scip-python", NOT_TRUSTED)
        if not shutil.which("node", path=sandbox._host_path(os.environ)):
            return self._skip(ctx, "scip-python", NO_NODE)

        def go():
            version = ctx.tool_versions.get("scip-python") or next(t["version"] for t in toolcheck.load_tools()["tools"] if t["id"] == "scip-python")
            index_js = scip_tool.ensure_installed(ctx.run, ctx.area.parent, version, timeout)
            extra = {}
            if st["folder"]:
                extra = {"cwd": ctx.checkout / st["folder"], "project_name": f"{ctx.repo_name}-{st['folder'].replace('/', '-')}",
                         "venv": self._venv(ctx, st["folder"])}
            index = scip_tool.run_index(ctx.run, index_js, ctx.checkout, ctx.area, ctx.repo_name, ctx.sha, timeout, **extra)
            symbols = scip_read.reduce(scip_read.decode(index.read_bytes()))
            for sym in symbols:
                if isinstance(sym.get("path"), str):
                    sym["path"] = self._lift(st, sym["path"])
            return symbols
        out["symbols"] += self._step(ctx, "scip-python", go) or []

    # ------------------------------------------------------------ entry

    @staticmethod
    def _lift(st, path):
        """A project-relative path as a repository-relative one."""
        return f"{st['folder']}/{path}" if st["folder"] else path

    @staticmethod
    def _local(st, path):
        """A repository-relative path as a project-relative one."""
        return path[len(st["folder"]) + 1:] if st["folder"] and path.startswith(st["folder"] + "/") else path

    @staticmethod
    def _venv(ctx, folder):
        """The nearest `.venv` at or above the project folder, as a path; the root one when none exists."""
        while folder:
            if (ctx.checkout / folder / ".venv").is_dir():
                return ctx.checkout / folder / ".venv"
            folder = folder.rpartition("/")[0]
        return ctx.checkout / ".venv"

    @staticmethod
    def _merge_status(statuses) -> dict:
        """One status per tool across projects: a failure wins, then ok, then skipped."""
        merged = {}
        for status in statuses:
            for tool, st in status.items():
                old = merged.get(tool)
                if old is None or (st["status"], old["status"]) in (("failed", "ok"), ("failed", "skipped"), ("ok", "skipped")):
                    merged[tool] = st
        return merged

    def _extract_project(self, ctx, proj, timeout) -> dict:
        folder = proj["dir"]
        prefix = folder + "/" if folder else ""
        view = ctx.checkout / folder if folder else ctx.checkout
        vtree = frozenset(p[len(prefix):] for p in ctx.tree if p.startswith(prefix)) if folder else ctx.tree
        out = {o: [] for o in OUTPUTS}
        mine = set(proj["files"])
        files = [p for p in ctx.files if p in mine]
        roots = py_packages.package_roots(vtree, view)
        loose = [prefix + p for p in py_packages.loose_modules(vtree, roots)]
        roots = [{"root": (prefix + r["root"]).rstrip("/"), "package": r["package"]} for r in roots]
        tests = [p for p in files if gather.TEST_RE.search(p)]
        contracts = py_packages.importlinter_contracts(view)
        contracts["contracts"] = [{**c, "path": prefix + c["path"]} for c in contracts["contracts"]]
        st = {"roots": roots, "loose": [p for p in loose if p in mine], "contracts": contracts, "vulture": py_packages.vulture_config(view),
              "tests": tests, "src": [p for p in files if p not in set(tests)], "module_paths": {}, "source": {}, "folder": folder,
              "view": view, "files": files}
        for item in py_packages.test_configs(view, vtree):
            out["tests"].append({**item, "path": prefix + item["path"]})
        self._graph(ctx, out, st, timeout)
        self._syntax(ctx, out, st)
        st["path_module"] = {p: m for m, p in st["module_paths"].items()}
        self._semgrep(ctx, out, st)
        self._entries(ctx, out, st)
        self._dead(ctx, out, st, timeout)
        self._symbols(ctx, out, st, timeout)
        return out

    def extract(self, ctx) -> dict:
        timeout = config.timeouts()["tool"]
        projects = py_project.projects(ctx.tree)
        owner = {p: proj["dir"] for proj in projects for p in proj["files"]}
        for proj in projects:
            proj["files"] = [p for p in sorted(set(ctx.files) | set(proj["files"])) if owner.get(p, "") == proj["dir"]]
        out = {o: [] for o in OUTPUTS}
        statuses = []
        for proj in projects:
            if len(projects) > 1 and not (proj["files"] or proj["manifests"]):
                continue
            sub = copy.copy(ctx)
            sub.tool_status = {}
            part = self._extract_project(sub, proj, timeout)
            statuses.append(sub.tool_status)
            for o, items in part.items():
                out[o] += [{**i, "project": proj["dir"]} for i in items] if proj["dir"] else items
        ctx.tool_status.update(self._merge_status(statuses))
        return {o: candidates.sort_items(items) for o, items in out.items()}
