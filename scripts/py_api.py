"""What a Python library offers to other packages: its public API (D10 of plan 012).

Pure functions over the tracked paths and a `read(path)` that returns a file's text or None. Standard library only; the
source is read with `ast` and never run. Rows are `public-api` symbols with the same keys the JavaScript and C# readers write.
"""
from __future__ import annotations

import ast
import configparser
import re
import tomllib

import gather

MAX_HOPS = 10
SCRIPT_GROUPS = ("scripts", "gui-scripts", "console_scripts", "gui_scripts")


def _toml(read, path):
    try:
        return tomllib.loads(read(path) or "")
    except tomllib.TOMLDecodeError:
        return {}


def _ini(read, path):
    cfg = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        cfg.read_string(read(path) or "")
    except configparser.Error:
        return configparser.ConfigParser()
    return cfg


def _manifest(project, name):
    return next((m for m in project["manifests"] if m.rpartition("/")[2] == name), None)


def _lines(value) -> list:
    return [v.strip() for v in str(value).splitlines() if v.strip()]


def _scripts_declared(project, read) -> bool:
    toml = _manifest(project, "pyproject.toml")
    data = _toml(read, toml) if toml else {}
    if any(data.get("project", {}).get(k) for k in ("scripts", "gui-scripts")) or data.get("tool", {}).get("poetry", {}).get("scripts"):
        return True
    cfg_path = _manifest(project, "setup.cfg")
    if cfg_path:
        cfg = _ini(read, cfg_path)
        if any(cfg.get("options.entry_points", k, fallback="").strip() for k in ("console_scripts", "gui_scripts")):
            return True
    setup = _manifest(project, "setup.py")
    return bool(setup and re.search(r"console_scripts|gui_scripts", read(setup) or ""))


def _packable(project, read) -> bool:
    toml = _manifest(project, "pyproject.toml")
    if toml and "build-system" in _toml(read, toml):
        return True
    cfg_path = _manifest(project, "setup.cfg")
    return bool(_manifest(project, "setup.py") or (cfg_path and _ini(read, cfg_path).has_section("metadata")))


def is_library(project, read, tree=()) -> bool:
    """Packable, and either typed (`py.typed`) or declaring no console or GUI scripts. Anything else is an application."""
    if not _packable(project, read):
        return False
    prefix = project["dir"] + "/" if project["dir"] else ""
    typed = any(t.startswith(prefix) and t.endswith("/py.typed") and not gather.TEST_RE.search(t) for t in tree)
    return typed or not _scripts_declared(project, read)


def distribution_name(project, read) -> str:
    toml = _manifest(project, "pyproject.toml")
    data = _toml(read, toml) if toml else {}
    name = data.get("project", {}).get("name") or data.get("tool", {}).get("poetry", {}).get("name")
    cfg_path = _manifest(project, "setup.cfg")
    if not name and cfg_path:
        name = _ini(read, cfg_path).get("metadata", "name", fallback=None)
    setup = _manifest(project, "setup.py")
    if not name and setup:
        try:
            for node in ast.walk(ast.parse(read(setup) or "")):
                if isinstance(node, ast.Call):
                    name = next((k.value.value for k in node.keywords if k.arg == "name" and isinstance(k.value, ast.Constant)), None)
                    if name:
                        break
        except SyntaxError:
            pass
    return str(name) if name else project["dir"].rpartition("/")[2]


# ------------------------------------------------------------------ reading one module


def _strings(node):
    """A list of string literals from a list, a tuple or a sum of them; None when it is anything else."""
    if isinstance(node, (ast.List, ast.Tuple)) and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts):
        return [e.value for e in node.elts]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _strings(node.left), _strings(node.right)
        return left + right if left is not None and right is not None else None
    return None


def _is_all(node) -> bool:
    return isinstance(node, ast.Name) and node.id == "__all__"


def _type_checking(node) -> bool:
    t = node.test
    return (isinstance(t, ast.Name) and t.id == "TYPE_CHECKING") or (isinstance(t, ast.Attribute) and t.attr == "TYPE_CHECKING")


def _statements(body):
    for node in body:
        if isinstance(node, ast.If):
            if not _type_checking(node):
                yield from _statements(node.body + node.orelse)
        elif isinstance(node, ast.Try):
            yield from _statements(node.body + node.orelse + node.finalbody)
        else:
            yield node


def _bound(target):
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, (ast.Tuple, ast.List)):
        for e in target.elts:
            yield from _bound(e)


class Module:
    """The names one module binds at its top level and how it re-exports others."""

    def __init__(self, dotted, path, text, is_package):
        self.dotted, self.path, self.is_package = dotted, path, is_package
        self.all, self.dynamic = None, False
        self.defs, self.imports, self.stars = {}, {}, []
        try:
            body = ast.parse(text).body
        except (SyntaxError, ValueError):
            body = []
        for node in _statements(body):
            self._read(node)

    def _target(self, level, module):
        parts = self.dotted.split(".") if self.is_package else self.dotted.split(".")[:-1]
        parts = parts[:len(parts) - (level - 1)] if level > 1 else parts
        return ".".join(parts + ([module] if module else []))

    def _read(self, node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            self.defs[node.name] = (node.lineno, "class" if isinstance(node, ast.ClassDef) else "function")
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(_is_all(t) for t in targets):
                self._read_all(node)
            for t in targets:
                for name in _bound(t):
                    if name != "__all__" and not isinstance(node, ast.AugAssign):
                        self.defs[name] = (node.lineno, "variable")
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            f = node.value.func
            if isinstance(f, ast.Attribute) and _is_all(f.value) and f.attr == "extend" and node.value.args:
                self._extend(_strings(node.value.args[0]))
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == "*":
                    if node.level:
                        self.stars.append(self._target(node.level, node.module))
                    continue
                kind, target = ("rel", self._target(node.level, node.module)) if node.level else ("abs", node.module or "")
                self.imports[a.asname or a.name] = (kind, target, a.name, node.lineno)

    def _read_all(self, node):
        value = getattr(node, "value", None)
        found = _strings(value) if value is not None else None
        if isinstance(node, ast.AugAssign):
            self._extend(found)
        elif found is None:
            self.dynamic = True
        else:
            self.all = list(found)

    def _extend(self, names):
        if names is None:
            self.dynamic = True
        else:
            self.all = (self.all or []) + names


# ------------------------------------------------------------------ a project's modules


class Package:
    """Every importable module of a project's top-level packages, and the answers about their names."""

    def __init__(self, roots, tree, read):
        self.read, self.tree, self.mods, self.typed, self._cache = read, tree, {}, set(), {}
        for r in roots:
            base = r["root"] + "/" if r["root"] else ""
            head = base + r["package"] + "/"
            if head + "py.typed" in tree:
                self.typed.add(r["package"])
            for t in sorted(tree):
                if not t.startswith(head) or not t.endswith((".py", ".pyi")) or gather.TEST_RE.search(t) or gather.noise_reason(t):
                    continue
                parts = t[len(base):].rsplit(".", 1)[0].split("/")
                is_pkg = parts[-1] == "__init__"
                dotted = ".".join(parts[:-1] if is_pkg else parts)
                self.mods.setdefault(dotted, {"is_package": is_pkg})["pyi" if t.endswith(".pyi") else "py"] = t

    def source(self, dotted):
        entry = self.mods.get(dotted)
        return (entry.get("py") or entry.get("pyi")) if entry else None

    def module(self, dotted):
        if dotted not in self._cache:
            path = self.source(dotted)
            self._cache[dotted] = Module(dotted, path, self.read(path) or "", self.mods[dotted]["is_package"]) if path else None
        return self._cache[dotted]

    def exported(self, dotted, hops=0, seen=()) -> list:
        """The names a module offers: `__all__`, or else its public names, relative re-exports and star re-exports."""
        m = self.module(dotted)
        if m is None or hops > MAX_HOPS or dotted in seen:
            return []
        if m.all is not None:
            return list(dict.fromkeys(m.all))
        names = [n for n in m.defs if not n.startswith("_")]
        names += [n for n, (kind, *_rest) in m.imports.items() if kind == "rel" and not n.startswith("_")]
        for target in m.stars:
            names += self.exported(target, hops + 1, (*seen, dotted))
        return list(dict.fromkeys(names))

    def resolve(self, dotted, name, hops=0, seen=frozenset()) -> dict:
        """Where a name is defined: {"path", "line", "kind", "external"}. A name that leaves the project has no path."""
        m = self.module(dotted)
        gone = {"path": None, "line": None, "kind": "variable", "external": dotted}
        if m is None or hops > MAX_HOPS or (dotted, name) in seen:
            return gone
        seen = seen | {(dotted, name)}
        if name in m.defs:
            return {"path": m.path, "line": m.defs[name][0], "kind": m.defs[name][1], "external": None}
        if name in m.imports:
            kind, target, orig, line = m.imports[name]
            if kind == "abs":
                return {**gone, "external": target}
            if f"{target}.{orig}" in self.mods:
                return {"path": self.source(f"{target}.{orig}"), "line": 1, "kind": "module", "external": None}
            return self.resolve(target, orig, hops + 1, seen) if target in self.mods else {**gone, "external": target}
        for target in m.stars:
            if name in self.exported(target):
                return self.resolve(target, name, hops + 1, seen)
        return {"path": m.path, "line": 1, "kind": "variable", "external": None}


# ------------------------------------------------------------------ rows


def _find_line(text, name) -> int:
    for i, line in enumerate((text or "").splitlines(), 1):
        if re.search(r"^\s*[\"']?" + re.escape(name) + r"[\"']?\s*[=:]", line):
            return i
    return 1


def _entry_point_rows(project, read, package) -> list:
    groups = []  # (group, name, target, path)
    toml = _manifest(project, "pyproject.toml")
    if toml:
        for group, table in (_toml(read, toml).get("project", {}).get("entry-points", {}) or {}).items():
            groups += [(group, n, str(t), toml) for n, t in table.items()]
    cfg_path = _manifest(project, "setup.cfg")
    if cfg_path:
        cfg = _ini(read, cfg_path)
        if cfg.has_section("options.entry_points"):
            for group, value in cfg.items("options.entry_points"):
                for entry in _lines(value):
                    n, _, t = entry.partition("=")
                    groups.append((group, n.strip(), t.strip(), cfg_path))
    rows = []
    for group, name, target, path in groups:
        if group in SCRIPT_GROUPS:
            continue
        module = target.split(":")[0].split("[")[0].strip()
        rows.append({"kind": "public-api", "path": path, "line": _find_line(read(path), name), "name": name, "symbol_kind": f"entry point ({group})",
                     "package": package, "subpath": module, "audience": "entry point group", "external": None})
    return rows


def items(project, roots, tree, read) -> tuple:
    """(`public-api` symbols, `py-note` items for modules whose `__all__` could not be read) for one Python project."""
    package = distribution_name(project, read)
    pkg, symbols, notes = Package(roots, tree, read), [], []
    for dotted in sorted(pkg.mods):
        if any(part.startswith("_") for part in dotted.split(".")):
            continue
        m = pkg.module(dotted)
        if m is None:
            continue
        if m.dynamic:
            notes.append({"kind": "py-note", "path": m.path, "note": "api", "name": f"{package}|{dotted}"})
            continue
        entry = pkg.mods[dotted]
        top = dotted.split(".")[0]
        audience = "listed in __all__" if m.all is not None else "public by name"
        audience += (", typed" if top in pkg.typed else "") + (", has a stub" if "py" in entry and "pyi" in entry else "")
        for name in pkg.exported(dotted):
            where = pkg.resolve(dotted, name)
            symbols.append({"kind": "public-api", "path": where["path"], "line": where["line"], "name": name, "symbol_kind": where["kind"],
                            "package": package, "subpath": dotted, "audience": audience, "external": where["external"]})
    symbols += _entry_point_rows(project, read, package)
    return sorted(symbols, key=lambda s: (s["package"], s["subpath"], s["name"])), notes
