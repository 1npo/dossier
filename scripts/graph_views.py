"""Collapsible views of the component and module graphs (plan 012, D7). Pure Python, standard library only.

`views(levels, edges, title)` turns a hierarchy and the import edges between its leaves into a list of views. Each view holds
at most `MAX_NODES` nodes and `MAX_EDGES` edges, so a reader never meets a picture too big to read. A node that has children
has a view of its own; folding many children into group nodes is collapsing, so every leaf is still reachable through a view.
The browser only switches between the views that are computed here.
"""
from __future__ import annotations

MAX_NODES = 12
MAX_EDGES = 30
GROUP_SIZE = 10
KINDS = ("area", "component", "module")


def _mermaid_id(name: str, taken: dict) -> str:
    import measured_graph  # imported late: measured_graph imports this module

    return measured_graph.mermaid_id(name, taken)


def _label(text: str) -> str:
    return str(text).replace('"', "#quot;")


class _Hierarchy:
    def __init__(self, levels: dict):
        self.levels = levels
        self.children: dict = {}
        for node, parent in sorted(levels.items(), key=lambda kv: str(kv[0])):
            self.children.setdefault(parent, []).append(node)
        self._depth: dict = {}

    def depth(self, node) -> int:
        if node not in self._depth:
            parent = self.levels.get(node)
            self._depth[node] = 0 if parent is None else self.depth(parent) + 1
        return self._depth[node]

    def at(self, node, depth: int):
        """The ancestor of `node` at `depth`, or the node itself when it sits higher than that."""
        while self.depth(node) > depth:
            node = self.levels[node]
        return node


def _fold(items: list, limit: int) -> list:
    """Node specs for a view: one per item, or groups of at most GROUP_SIZE in name order (groups of groups when there are many)."""
    specs = [{"label": str(i), "items": [i], "sub": None} for i in items]
    while len(specs) > limit:
        chunks = [specs[i:i + GROUP_SIZE] for i in range(0, len(specs), GROUP_SIZE)]
        specs = [{"label": f"{c[0]['label']} … {c[-1]['label']} ({sum(len(s['items']) for s in c)})",
                  "items": [i for s in c for i in s["items"]], "sub": c} for c in chunks]
    return specs


def _threshold(weights: list) -> int:
    w = 1
    while sum(1 for x in weights if x >= w) > MAX_EDGES:
        w += 1
    return w


def _src(view: dict) -> str:
    lines = ["flowchart LR"]
    lines += [f'  {n["id"]}["{_label(n["label"])}"]' for n in view["nodes"]]
    lines += [f'  {e["from"]} -->|{e["weight"]}| {e["to"]}' for e in view["edges"]]
    return "\n".join(lines)


def mermaid(view: dict) -> str:
    """The Mermaid source of a view (`flowchart LR`, one line per node and per edge)."""
    return _src(view)


def views(levels: dict, edges: dict, title: str, kinds: tuple = KINDS) -> list:
    """Every view of a hierarchy, the root view first.

    `levels` is {node: parent} with None for top-level nodes; `edges` is {(a, b): weight} between leaf nodes.
    A view is {"id", "title", "parent", "children": [view ids], "nodes", "edges", "hidden", "src"}; a node is
    {"id", "label", "kind", "view"} and an edge {"from", "to", "weight"}.
    """
    h = _Hierarchy(levels)
    leaves = [(a, b, w) for (a, b), w in sorted(edges.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))) if a in levels and b in levels and a != b]
    out: list = []

    def noun(depth: int) -> str:
        return kinds[min(depth, len(kinds) - 1)]

    def build(scope: list, specs, cd: int, name: str, parent_id) -> str:
        """One view. `scope` is every sibling item of the focus; `specs` the node specs shown (None: fold the scope here)."""
        vid = f"v{len(out)}"
        view = {"id": vid, "title": name, "parent": parent_id, "children": [], "nodes": [], "edges": [], "hidden": None, "src": ""}
        out.append(view)
        scope_set = set(scope)

        def outside(leaf):
            return h.at(leaf, cd - 1) if cd > 0 else None

        if specs is None:
            touches = any((h.at(a, cd) in scope_set) != (h.at(b, cd) in scope_set) for a, b, _ in leaves) if cd > 0 else False
            specs = _fold(scope, MAX_NODES - 1 if touches else MAX_NODES)
        taken: dict = {}
        nodes, key_of = [], {}
        for spec in specs:
            single = spec["sub"] is None
            kind, key = (noun(cd), "i:") if single else ("group", "g:")
            node = {"id": _mermaid_id(key + spec["label"], taken), "label": spec["label"], "kind": kind, "view": None, "_spec": spec}
            nodes.append(node)
            for i in spec["items"]:
                key_of[i] = node["id"]

        def node_for(leaf):
            item = h.at(leaf, cd)
            if item in key_of:
                return key_of[item]
            if item in scope_set:
                return "sibling"
            x = outside(leaf)
            return None if x is None else ("ext", x)

        raw: dict = {}
        for a, b, w in leaves:
            if h.at(a, cd) not in key_of and h.at(b, cd) not in key_of:
                continue
            ka, kb = node_for(a), node_for(b)
            if ka is None or kb is None or ka == kb:
                continue
            raw[(ka, kb)] = raw.get((ka, kb), 0) + w
        used = {k for pair in raw for k in pair}
        resolved: dict = {}
        if "sibling" in used:
            n_sib = sum(1 for i in scope if i not in key_of)
            resolved["sibling"] = {"id": _mermaid_id("other:sibling", taken), "label": f"{n_sib} other {noun(cd)}s", "kind": "other", "view": None}
            nodes.append(resolved["sibling"])
        ext_used = sorted(k[1] for k in used if isinstance(k, tuple))
        if ext_used:
            if len(nodes) + len(ext_used) > MAX_NODES:
                other = {"id": _mermaid_id("other:external", taken), "label": f"{len(ext_used)} other {noun(cd - 1)}s", "kind": "other", "view": None}
                nodes.append(other)
                resolved.update({("ext", x): other["id"] for x in ext_used})
            else:
                for x in ext_used:
                    node = {"id": _mermaid_id("x:" + str(x), taken), "label": str(x), "kind": noun(cd - 1), "view": None}
                    nodes.append(node)
                    resolved[("ext", x)] = node["id"]
        resolved = {k: (v["id"] if isinstance(v, dict) else v) for k, v in resolved.items()}
        agg: dict = {}
        for (ka, kb), w in raw.items():
            fa, fb = resolved.get(ka, ka), resolved.get(kb, kb)
            if fa != fb:
                agg[(fa, fb)] = agg.get((fa, fb), 0) + w
        order = {n["id"]: i for i, n in enumerate(nodes)}
        keep = sorted(agg.items(), key=lambda kv: (order[kv[0][0]], order[kv[0][1]]))
        if len(keep) > MAX_EDGES:
            w = _threshold(list(agg.values()))
            total = len(keep)
            keep = [kv for kv in keep if kv[1] >= w]
            view["hidden"] = {"w": w, "shown": len(keep), "total": total}
        view["edges"] = [{"from": a, "to": b, "weight": wt} for (a, b), wt in keep]
        view["nodes"] = nodes
        for node in nodes:
            spec = node.pop("_spec", None)
            if spec is None:
                continue
            if spec["sub"] is not None:
                node["view"] = build(scope, spec["sub"], cd, spec["label"], vid)
            elif h.children.get(spec["items"][0]):
                kids = h.children[spec["items"][0]]
                node["view"] = build(kids, None, cd + 1, spec["label"], vid)
            if node["view"]:
                view["children"].append(node["view"])
        view["src"] = _src(view)
        return vid

    roots = h.children.get(None, [])
    if roots:
        build(roots, None, 0, title, None)
    return out
