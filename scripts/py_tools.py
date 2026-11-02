"""Clients for the locked Python worker (grimp and vulture), in the style of `shared_tools`."""
from __future__ import annotations

from shared_tools import ToolError, _call  # noqa: F401  (ToolError is re-exported for callers)


class Grimp:
    def __init__(self, run, timeout: float):
        self.run, self.timeout = run, timeout

    def graph(self, roots: list, packages: list, contracts: list) -> dict:
        """Modules, imports and contract results. Raises ToolError when the worker fails or reports errors with no modules."""
        res = _call(self.run, "grimp", "py_worker.py",
                    {"mode": "graph", "roots": roots, "packages": packages, "contracts": contracts}, timeout=self.timeout)
        if res.get("errors") and not res.get("modules"):
            raise ToolError("grimp could not build the import graph: " + res["errors"][0])
        return res


class Vulture:
    def __init__(self, run, timeout: float):
        self.run, self.timeout = run, timeout

    def dead(self, paths: list, config: dict) -> list:
        req = {"mode": "dead", "paths": paths, "ignore_names": config.get("ignore_names", []),
               "ignore_decorators": config.get("ignore_decorators", []), "min_confidence": config.get("min_confidence", 60)}
        return _call(self.run, "vulture", "py_worker.py", req, timeout=self.timeout)["items"]
