"""A standard-library reader for the SCIP index file (protobuf wire format) written by scip-python.

Only the fields dossier needs are read: documents, occurrences (range, symbol, roles, enclosing range) and symbol
information (kind, display name). Everything else is skipped. See https://github.com/sourcegraph/scip (scip.proto).
"""
from __future__ import annotations

import re

DEFINITION = 1
DESCRIPTOR = re.compile(r"(`(?:[^`]|``)*`|[\w$+\-<>_]+)(\([^)]*\)\.|\[[^\]]*\]|[/#.:!])")


def _varint(data: bytes, i: int) -> tuple:
    shift = value = 0
    while True:
        b = data[i]
        i += 1
        value |= (b & 0x7F) << shift
        if not b & 0x80:
            return value, i
        shift += 7


def _fields(data: bytes):
    """Yield (field number, wire type, value) for a message. Fixed-width values are skipped."""
    i = 0
    while i < len(data):
        key, i = _varint(data, i)
        num, wire = key >> 3, key & 7
        if wire == 0:
            value, i = _varint(data, i)
        elif wire == 2:
            size, i = _varint(data, i)
            value, i = data[i:i + size], i + size
        elif wire == 1:
            i += 8
            continue
        elif wire == 5:
            i += 4
            continue
        else:
            raise ValueError(f"unsupported wire type {wire}")
        yield num, wire, value


def _ints(wire: int, value) -> list:
    """A repeated int32 field element: one varint, or a packed run of varints."""
    if wire == 0:
        return [value]
    out, i = [], 0
    while i < len(value):
        n, i = _varint(value, i)
        out.append(n)
    return out


def _range(nums: list):
    """Four-element zero-based range from a 3 or 4 element one; None for anything else."""
    if len(nums) == 3:
        return [nums[0], nums[1], nums[0], nums[2]]
    return list(nums) if len(nums) == 4 else None


def _occurrence(data: bytes) -> dict:
    rng, enclosing, alt, symbol, roles = [], [], [], "", 0
    for num, wire, value in _fields(data):
        if num == 1:
            rng += _ints(wire, value)
        elif num == 2:
            symbol = value.decode("utf-8", "replace")
        elif num == 3:
            roles = value
        elif num == 7:
            enclosing += _ints(wire, value)
        elif num in (8, 9) and wire == 2:  # typed ranges: newer scip-python only; read as packed numbers
            alt += _ints(wire, value)
    return {"range": _range(rng) or _range(alt), "symbol": symbol, "roles": roles, "enclosing_range": _range(enclosing)}


def _symbol_info(data: bytes) -> dict:
    info = {"symbol": "", "kind": 0, "display_name": ""}
    for num, wire, value in _fields(data):
        if num == 1:
            info["symbol"] = value.decode("utf-8", "replace")
        elif num == 5:
            info["kind"] = value
        elif num == 6:
            info["display_name"] = value.decode("utf-8", "replace")
    return info


def decode(data: bytes) -> dict:
    """{"documents": [{"path", "occurrences": [...], "symbols": [...]}]}"""
    documents = []
    for num, wire, value in _fields(data):
        if num != 2:
            continue
        doc = {"path": "", "occurrences": [], "symbols": []}
        for n, w, v in _fields(value):
            if n == 1:
                doc["path"] = v.decode("utf-8", "replace")
            elif n == 2:
                doc["occurrences"].append(_occurrence(v))
            elif n == 3:
                doc["symbols"].append(_symbol_info(v))
        documents.append(doc)
    return {"documents": documents}


def descriptors(symbol: str) -> list:
    """[(name, suffix)] of a SCIP symbol string: 'pkg/a/f().' -> [('pkg', '/'), ('a', '/'), ('f', '().')]."""
    parts = symbol.split(" ", 4)
    return [(m.group(1).strip("`"), m.group(2)) for m in DESCRIPTOR.finditer(parts[4])] if len(parts) == 5 else []


def descriptor_type(symbol: str) -> str:
    """class, method, function, variable or module, from the last descriptor of a symbol."""
    ds = descriptors(symbol)
    if not ds:
        return "variable"
    suffix = ds[-1][1]
    if suffix == "#":
        return "class"
    if suffix.startswith("("):
        return "method" if len(ds) > 1 and ds[-2][1] == "#" else "function"
    return "module" if suffix in ("/", ":") else "variable"


def _public(symbol: str) -> bool:
    ds = descriptors(symbol)
    return all(not name.startswith("_") for name, _ in ds) and sum(s not in ("/", ":") for _, s in ds) <= 2


def reduce(index: dict) -> list:
    """D2 'def' and 'ref-edge' items. Local symbols are skipped; lines are 1-based."""
    defined: dict = {}
    names = {s["symbol"]: s["display_name"] for d in index["documents"] for s in d["symbols"] if s["display_name"]}
    items = []
    for d in index["documents"]:
        for o in d["occurrences"]:
            if o["roles"] & DEFINITION and o["range"] and not o["symbol"].startswith("local ") and o["symbol"] not in defined:
                end = (o["enclosing_range"] or o["range"])[2]
                ds = descriptors(o["symbol"])
                items.append({"kind": "def", "path": d["path"], "line": o["range"][0] + 1, "end_line": end + 1,
                              "name": names.get(o["symbol"]) or (ds[-1][0] if ds else o["symbol"]), "symbol": o["symbol"],
                              "type": descriptor_type(o["symbol"]), "public": _public(o["symbol"]), "refs": 0})
                defined[o["symbol"]] = d["path"]
    by_symbol = {i["symbol"]: i for i in items}
    edges: dict = {}
    for d in index["documents"]:
        for o in d["occurrences"]:
            home = defined.get(o["symbol"])
            if o["roles"] & DEFINITION or home is None or home == d["path"]:
                continue
            by_symbol[o["symbol"]]["refs"] += 1
            edges[(d["path"], home)] = edges.get((d["path"], home), 0) + 1
    items += [{"kind": "ref-edge", "path": src, "paths": [dst], "count": n} for (src, dst), n in edges.items()]
    return sorted(items, key=lambda i: (i["kind"], i["path"], i.get("line", 0), i.get("name", ""), i.get("paths", [""])[0]))
