# /// script
# requires-python = ">=3.10"
# dependencies = ["grimp==3.17", "vulture==2.16"]
# ///
"""Python worker: grimp import graph and vulture unused code. Reads one JSON request on stdin, prints one JSON object.

Request (graph): {"mode": "graph", "roots": [abs folders], "packages": [...], "contracts": [...]}
Response:        {"modules": [{"module", "path", "is_package"}], "imports": [{"from", "to", "lines"}],
                  "contracts": [{"name", "type", "status", "violations": [{"from", "to", "line"}], "reason"}], "errors": [...]}
Request (dead):  {"mode": "dead", "paths": [...], "ignore_names": [...], "ignore_decorators": [...], "min_confidence": 60}
Response:        {"items": [{"path", "line", "end_line", "name", "type", "confidence", "message"}]}
Nothing is imported or run from the repository: grimp parses the source and vulture uses `ast`. The grimp cache is off.
"""
import json
import os
import sys

NOT_CHECKED = "dossier checks only layers and forbidden contracts."


def module_path(name, roots):
    """(path, is_package) of a module from its dotted name and the root folders; never imports anything."""
    parts = name.split(".")
    for root in roots:
        base = os.path.join(root, *parts)
        if os.path.isfile(os.path.join(base, "__init__.py")):
            return os.path.join(base, "__init__.py"), True
        if os.path.isfile(base + ".py"):
            return base + ".py", False
    return None, False


def layer_names(entry):
    """Split one import-linter layer line into (names, independent). `(x)` marks an optional layer."""
    independent = "|" in entry
    sep = "|" if independent else ":"
    return [n.strip().strip("()") for n in entry.split(sep) if n.strip()], independent


def first_line(graph, importer, imported):
    details = graph.get_import_details(importer=importer, imported=imported)
    return min((d["line_number"] for d in details), default=0)


def build_layers(grimp, entries, modules, containers):
    layers = []
    for entry in entries:
        names, independent = layer_names(entry)
        present = [n for n in names if n in modules or any(c + "." + n in modules for c in containers)]
        if not present:
            continue
        layers.append(grimp.Layer(*present, independent=independent) if len(names) > 1 else present[0])
    return layers


def check_layers(grimp, graph, contract):
    containers = set(contract.get("containers") or [])
    modules = set(graph.modules)
    layers = build_layers(grimp, contract.get("layers") or [], modules, containers)
    broken = graph.find_illegal_dependencies_for_layers(layers=layers, containers=containers or None)
    violations = set()
    for dep in broken:
        for route in dep.routes:
            for head in route.heads:
                for tail in route.tails:
                    nxt = route.middle[0] if route.middle else tail
                    violations.add((head, nxt, first_line(graph, head, nxt)))
    return [{"from": f, "to": t, "line": n} for f, t, n in sorted(violations)]


def check_forbidden(graph, contract):
    violations = set()
    for source in contract.get("source_modules") or []:
        for forbidden in contract.get("forbidden_modules") or []:
            if source in graph.modules and forbidden in graph.modules and graph.chain_exists(importer=source, imported=forbidden, as_packages=True):
                chains = sorted(graph.find_shortest_chains(importer=source, imported=forbidden, as_packages=True), key=lambda c: (len(c), c))
                if chains:
                    first, second = chains[0][0], chains[0][1]
                    violations.add((first, second, first_line(graph, first, second)))
    return [{"from": f, "to": t, "line": n} for f, t, n in sorted(violations)]


def evaluate(grimp, graph, contract):
    res = {"name": contract.get("name", ""), "type": contract.get("type", ""), "status": "not-checked", "violations": [], "reason": NOT_CHECKED}
    try:
        if res["type"] == "layers":
            found = check_layers(grimp, graph, contract)
        elif res["type"] == "forbidden":
            found = check_forbidden(graph, contract)
        else:
            return res
    except Exception as e:  # a bad contract must not lose the graph
        res["reason"] = "grimp could not check this contract: " + (str(e).splitlines() or [type(e).__name__])[0]
        return res
    res.update(status="broken" if found else "kept", violations=found, reason=None)
    return res


def graph_mode(req):
    import grimp

    roots = [os.path.abspath(r) for r in req.get("roots", [])]
    for root in reversed(roots):
        sys.path.insert(0, root)
    try:
        graph = grimp.build_graph(*req["packages"], include_external_packages=False,
                                  exclude_type_checking_imports=False, cache_dir=None)
    except Exception as e:
        return {"modules": [], "imports": [], "contracts": [], "errors": [(str(e).splitlines() or [type(e).__name__])[0]]}
    modules = []
    for name in sorted(graph.modules):
        path, is_package = module_path(name, roots)
        modules.append({"module": name, "path": path, "is_package": is_package})
    imports = []
    for importer in sorted(graph.modules):
        for imported in sorted(graph.find_modules_directly_imported_by(importer)):
            lines = sorted({d["line_number"] for d in graph.get_import_details(importer=importer, imported=imported)})
            imports.append({"from": importer, "to": imported, "lines": lines})
    contracts = [evaluate(grimp, graph, c) for c in req.get("contracts", [])]
    return {"modules": modules, "imports": imports, "contracts": contracts, "errors": []}


def dead_mode(req):
    import vulture

    v = vulture.Vulture(ignore_names=req.get("ignore_names") or None, ignore_decorators=req.get("ignore_decorators") or None)
    v.scavenge(req.get("paths", []))
    items = [{"path": str(i.filename), "line": i.first_lineno, "end_line": i.last_lineno, "name": i.name, "type": i.typ,
              "confidence": i.confidence, "message": i.message}
             for i in v.get_unused_code(min_confidence=req.get("min_confidence", 60))]
    return {"items": sorted(items, key=lambda i: (i["path"], i["line"], i["name"]))}


def main():
    req = json.load(sys.stdin)
    out = {"graph": graph_mode, "dead": dead_mode}[req["mode"]](req)
    json.dump(out, sys.stdout)


if __name__ == "__main__":
    main()
