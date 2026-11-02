"""Small graph helpers for the import graph: cycles, ranking, communities and grouping. Standard library only.

Everything here is deterministic: nodes are visited in sorted order and ties go to the smallest name.
"""
from __future__ import annotations


def _adjacency(edges) -> dict:
    adj: dict = {}
    for a, b in edges:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set())
    return adj


def cycles(edges: list) -> list:
    """Strongly connected components with more than one node (Tarjan, iterative). Each is sorted; the list is sorted."""
    adj = _adjacency(edges)
    index, low, on_stack, stack, found = {}, {}, set(), [], []
    counter = 0
    for root in sorted(adj):
        if root in index:
            continue
        work = [(root, iter(sorted(adj[root])))]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            node, children = work[-1]
            advanced = False
            for child in children:
                if child not in index:
                    index[child] = low[child] = counter
                    counter += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(sorted(adj[child]))))
                    advanced = True
                    break
                if child in on_stack:
                    low[node] = min(low[node], index[child])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                members = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    members.append(member)
                    if member == node:
                        break
                if len(members) > 1:
                    found.append(sorted(members))
    return sorted(found)


def pagerank(nodes, edges, damping: float = 0.85, rounds: int = 50) -> dict:
    """Importance of each node; an edge points from the importer to the imported. Dangling weight is spread evenly."""
    names = sorted(set(nodes) | {n for e in edges for n in e})
    if not names:
        return {}
    out = {n: set() for n in names}
    for a, b in edges:
        if a != b:
            out[a].add(b)
    size = len(names)
    rank = {n: 1.0 / size for n in names}
    for _ in range(rounds):
        dangling = sum(rank[n] for n in names if not out[n])
        fresh = {n: (1 - damping) / size + damping * dangling / size for n in names}
        for n in names:
            for m in out[n]:
                fresh[m] += damping * rank[n] / len(out[n])
        rank = fresh
    return rank


def communities(nodes, edges, rounds: int = 20) -> dict:
    """Label propagation on the undirected graph. Returns node -> label (the smallest name that won)."""
    names = sorted(set(nodes) | {n for e in edges for n in e})
    neighbours: dict = {n: set() for n in names}
    for a, b in edges:
        if a != b:
            neighbours[a].add(b)
            neighbours[b].add(a)
    label = {n: n for n in names}
    for _ in range(rounds):
        changed = False
        for n in names:
            if not neighbours[n]:
                continue
            counts: dict = {}
            for m in neighbours[n]:
                counts[label[m]] = counts.get(label[m], 0) + 1
            best = min(counts, key=lambda lab: (-counts[lab], lab))
            if best != label[n]:
                label[n] = best
                changed = True
        if not changed:
            break
    return label


def aggregate(edges, group_of: dict) -> dict:
    """Edge counts between groups. Edges inside one group and edges with an ungrouped end are dropped."""
    counts: dict = {}
    for a, b in edges:
        ga, gb = group_of.get(a), group_of.get(b)
        if ga is None or gb is None or ga == gb:
            continue
        counts[(ga, gb)] = counts.get((ga, gb), 0) + 1
    return counts
