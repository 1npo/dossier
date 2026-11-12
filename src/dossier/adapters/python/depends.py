"""FastAPI `Depends(...)` and `Security(...)`: a `ref-edge` from the function that declares a dependency to the file that defines it.

The blind-spot rule `dependency-injection` reports every `Depends(...)` and `Security(...)`. Where the dependency is a name that the
file imports from another file of the project, this module adds one `ref-edge` symbol for each (function, dependency) pair, so the
route reaches the dependency in the graph. A dependency that is an instance, `Depends(Auth())` or `Security(Auth(), scopes=[...])`,
counts as the class it calls. A dependency defined in the same file, a lambda and a name from outside the project add no edge.
"""
from __future__ import annotations

import ast
from collections.abc import Callable

__all__ = ["edges"]


INJECTORS = ("Depends", "Security")


def _is_depends(call: ast.Call) -> bool:
    f = call.func
    return (isinstance(f, ast.Name) and f.id in INJECTORS) or (isinstance(f, ast.Attribute) and f.attr in INJECTORS and isinstance(f.value, ast.Name) and f.value.id == "fastapi")


def _dependency(call: ast.Call):
    """The expression `Depends`/`Security` is given: the first argument or `dependency=`; a call (`Auth()`) stands for the callee."""
    arg = call.args[0] if call.args else next((k.value for k in call.keywords if k.arg == "dependency"), None)
    return arg.func if isinstance(arg, ast.Call) else arg


def _imports(tree: ast.Module, module: str, is_package: bool) -> dict:
    """Local name -> dotted name it stands for (`from a.b import c as d` gives `d: a.b.c`; `import a.b as m` gives `m: a.b`)."""
    package = module if is_package else module.rpartition(".")[0]
    names = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".") if package else []
                parts = parts[: len(parts) - (node.level - 1)] if node.level > 1 else parts
                base = ".".join(parts + ([node.module] if node.module else []))
            for a in node.names:
                names[a.asname or a.name] = f"{base}.{a.name}" if base else a.name
    return names


def _dotted(node) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _dotted(node.value)
        return f"{left}.{node.attr}" if left else None
    return None


def _target(name: str, imports: dict, module_paths: dict) -> str | None:
    """The project file that defines the dependency `name` as the importing file sees it, or None."""
    head, _, rest = name.partition(".")
    full = imports.get(head)
    if full is None:
        return None
    module = (f"{full}.{rest}" if rest else full).rpartition(".")[0]  # the last part is the dependency itself
    while module:
        if module in module_paths:
            return module_paths[module]
        module = module.rpartition(".")[0]
    return None


def _calls(func) -> list:
    """The `Depends(...)` and `Security(...)` calls in a function's decorators, parameter defaults and annotations and return annotation, which are not in a nested function."""
    found, stack = [], [*func.decorator_list, func.args, *([func.returns] if func.returns else [])]
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Call) and _is_depends(node):
            found.append(node)
        stack += list(ast.iter_child_nodes(node))
    return found


def edges(paths: list, read: Callable[[str], str], module_paths: dict, path_module: dict) -> list:
    """`ref-edge` symbols for the `Depends(name)` and `Security(name)` calls in `paths` (files the rule matched), in path and line order."""
    out = []
    for path in sorted(set(paths)):
        try:
            tree = ast.parse(read(path))
        except (OSError, SyntaxError, ValueError):
            continue
        module = path_module.get(path)
        if module is None:
            continue
        imports = _imports(tree, module, path.endswith("/__init__.py"))
        seen = {}
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for call in _calls(func):
                name = _dotted(_dependency(call))
                dst = _target(name, imports, module_paths) if name else None
                if not dst or dst == path:
                    continue
                key = (func.name, name)
                if key in seen:
                    seen[key]["count"] += 1
                else:
                    seen[key] = {"kind": "ref-edge", "path": path, "paths": [dst], "count": 1, "via": "fastapi-depends", "from": func.name,
                                 "to": name, "line": call.lineno}
        out += sorted(seen.values(), key=lambda e: (e["line"], e["from"]))
    return out
