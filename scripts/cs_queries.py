"""Tree-sitter queries for C#: declarations, usings, attributes and identifiers (plan 011, D14).

The worker returns flat captures (path, capture name, lines, columns, text) with no parent links. Each query therefore captures a
whole declaration, and `assemble` reads its head (the text before the body) with small scanners and joins declarations to the types
and namespaces that hold them by line range. `assemble` is pure, so unit tests use hand-made captures.
"""
from __future__ import annotations

import re

TYPE_NODES = ("class_declaration", "record_declaration", "struct_declaration", "interface_declaration", "enum_declaration")
MEMBER_NODES = {"method_declaration": "method", "constructor_declaration": "constructor", "property_declaration": "property",
                "field_declaration": "field", "event_field_declaration": "event", "enum_member_declaration": "enum-member",
                "delegate_declaration": "delegate"}
QUERY = "\n".join(
    [f"({n}) @type" for n in TYPE_NODES]
    + [f"({n}) @member.{kind}" for n, kind in MEMBER_NODES.items()]
    + ["(namespace_declaration) @ns", "(file_scoped_namespace_declaration) @ns", "(using_directive) @using",
       "(attribute_list) @attrlist", "(global_statement) @global", "(identifier) @ident", "(qualified_name) @qualified"])

COMPLEXITY_Q = ("[(if_statement) (for_statement) (foreach_statement) (while_statement) (do_statement) (switch_section) (switch_expression_arm) "
                "(catch_clause) (conditional_expression) (binary_expression operator: [\"&&\" \"||\" \"??\"])] @branch")
MODIFIERS = {"public", "private", "protected", "internal", "static", "abstract", "sealed", "partial", "readonly", "const", "virtual",
             "override", "async", "new", "extern", "unsafe", "volatile", "required", "file", "ref"}
KINDS = {"class": "class", "struct": "struct", "interface": "interface", "enum": "enum", "record": "record"}
FILE_END = 10 ** 9
PARAM_MODS = {"this", "ref", "out", "in", "params", "scoped", "readonly"}


# ---- text scanners ---------------------------------------------------------------------------------------------------

def _skip_string(text: str, i: int) -> int:
    """Index just after the string or character literal that starts at `i`."""
    quote, verbatim = text[i], i > 0 and text[i - 1] == "@"
    i += 1
    while i < len(text):
        if text[i] == "\\" and not verbatim:
            i += 2
            continue
        if text[i] == quote:
            if verbatim and text[i + 1:i + 2] == quote:
                i += 2
                continue
            return i + 1
        i += 1
    return i


def _end_of_head(text: str, stops: str) -> int:
    """Index of the first character in `stops` outside brackets and strings, or the length. `=` followed by `=` or `>` is not a stop unless `>` is."""
    depth, i = 0, 0
    while i < len(text):
        c = text[i]
        if c in "\"'":
            i = _skip_string(text, i)
            continue
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        elif depth == 0:
            if c == "=" and text[i + 1:i + 2] == ">" and "=>" in stops:
                return i
            if c == "=" and text[i + 1:i + 2] not in ("=", ">") and "=" in stops:
                return i
            if c in stops and c not in "=>":
                return i
        i += 1
    return len(text)


def _split(text: str, sep: str = ",") -> list:
    """Split at `sep` outside (), [], {}, <> and strings."""
    parts, depth, start, i = [], 0, 0, 0
    while i < len(text):
        c = text[i]
        if c in "\"'":
            i = _skip_string(text, i)
            continue
        if c in "([{<":
            depth += 1
        elif c in ")]}>" and not (c == ">" and text[i - 1:i] == "="):
            depth -= 1
        elif c == sep and depth == 0:
            parts.append(text[start:i])
            start = i + 1
        i += 1
    parts.append(text[start:])
    return [p.strip() for p in parts if p.strip()]


def strings_in(args: str) -> list:
    """The string literals in an attribute's argument text, in order, with their quotes removed."""
    out, i = [], 0
    while i < len(args):
        if args[i] == '"':
            end = _skip_string(args, i)
            out.append(args[i + 1:end - 1])
            i = end
        else:
            i += 1
    return out


def _attributes(head: str, line: int) -> tuple:
    """([attribute dict], the head with its attribute lists removed). `line` is the line the head starts on."""
    attrs, rest = [], head
    while True:
        stripped = rest.lstrip()
        if not stripped.startswith("["):
            break
        offset = len(head) - len(stripped)
        depth, i = 0, 0
        while i < len(stripped):
            if stripped[i] in "\"'":
                i = _skip_string(stripped, i)
                continue
            depth += stripped[i] == "["
            depth -= stripped[i] == "]"
            i += 1
            if depth == 0:
                break
        inner = stripped[1:i - 1]
        for part in _split(inner):
            part = re.sub(r"^\w+\s*:(?!:)", "", part).strip()
            found = re.match(r"([\w.]+)\s*(?:\((.*)\))?\s*$", part, re.S)
            if found:
                name = found.group(1).rsplit(".", 1)[-1]
                name = name[:-9] if name.endswith("Attribute") and len(name) > 9 else name
                attrs.append({"name": name, "args": (found.group(2) or "").strip(), "line": line + head.count("\n", 0, offset)})
        rest = stripped[i:]
    return attrs, rest.lstrip()


def _modifiers(text: str) -> tuple:
    """([modifier words at the front], the rest)."""
    words = []
    while True:
        found = re.match(r"(\w+)\s+", text)
        if not found or found.group(1) not in MODIFIERS:
            return words, text
        words.append(found.group(1))
        text = text[found.end():]


def _params(text: str) -> list:
    """Parameters from the text between the parentheses."""
    out = []
    for raw in _split(text):
        raw = _attributes(raw, 0)[1]
        raw = raw[:_end_of_head(raw, "=")].strip()
        tokens = raw.rsplit(None, 1)
        if len(tokens) != 2:
            continue
        words = tokens[0].split()
        out.append({"name": tokens[1], "type": " ".join(w for w in words if w not in PARAM_MODS), "this": "this" in words})
    return out


def _paren(text: str) -> tuple:
    """(the text inside the first top-level parentheses, the text after them), or (None, text)."""
    start = text.find("(")
    if start < 0:
        return None, text
    depth, i = 0, start
    while i < len(text):
        depth += text[i] == "("
        depth -= text[i] == ")"
        i += 1
        if depth == 0:
            return text[start + 1:i - 1], text[i:]
    return text[start + 1:], ""


def _bases(after_name: str) -> list:
    """Base types from the text after a type's name and parameters (`: A, B<T> where T : class`)."""
    after = re.split(r"\bwhere\b", after_name, maxsplit=1)[0]
    found = re.match(r"\s*(?:<[^:]*?>)?\s*:", after)
    if not found:
        found = re.search(r":", after)
        if not found:
            return []
    out = []
    for b in _split(after[found.end():]):
        b = re.sub(r"\(.*\)$", "", b, flags=re.S).strip()
        if b:
            out.append(b)
    return out


# ---- declarations ----------------------------------------------------------------------------------------------------

def _type(m: dict) -> dict | None:
    text = m["text"]
    head = text[:_end_of_head(text, "{;")]
    attrs, rest = _attributes(head, m["start_line"])
    mods, rest = _modifiers(rest)
    found = re.match(r"(class|struct|interface|enum|record)(?:\s+(?:class|struct))?\s+(\w+)\s*(.*)$", rest, re.S)
    if not found:
        return None
    inner, after = _paren(found.group(3)) if found.group(3).lstrip().startswith(("(", "<")) and "(" in found.group(3).split(":")[0] else (None, found.group(3))
    return {"name": found.group(2), "kind": KINDS[found.group(1)], "modifiers": mods, "line": m["start_line"], "end_line": m["end_line"],
            "attributes": attrs, "bases": _bases(after), "partial": "partial" in mods, "outer": None, "namespace": "",
            "params": _params(inner) if inner is not None and found.group(1) == "record" else [], "members": []}


def _member(m: dict, kind: str) -> dict | None:
    text = m["text"]
    attrs, rest = _attributes(text, m["start_line"])
    mods, rest = _modifiers(rest)
    base = {"kind": kind, "modifiers": mods, "line": m["start_line"], "end_line": m["end_line"], "attributes": attrs,
            "static": "static" in mods, "params": [], "type": None}
    if kind == "enum-member":
        found = re.match(r"(\w+)", rest)
        return {**base, "name": found.group(1)} if found else None
    if kind == "delegate":
        found = re.match(r"delegate\s+(.+?)\s+(\w+)\s*(?:<[^>]*>)?\s*\(", rest, re.S)
        return {**base, "name": found.group(2), "type": found.group(1).strip()} if found else None
    if kind in ("field", "event"):
        rest = re.sub(r"^event\s+", "", rest)
        first = _split(rest[:_end_of_head(rest, ";")])[0]
        found = re.match(r"(.+?)\s+(\w+)\s*(?:=\s*(.*))?$", first, re.S)
        if not found:
            return None
        return {**base, "name": found.group(2), "type": found.group(1).strip(), "init": (found.group(3) or "").strip()[:200]}
    stop = min(_end_of_head(rest, "{;"), _end_of_head(rest, "=>"), _end_of_head(rest, "=")) if kind == "property" else _end_of_head(rest, "{;")
    head = rest[:stop]
    if kind in ("method", "constructor"):
        inner, _ = _paren(head)
        before = head[:head.find("(")] if "(" in head else head
        before = re.sub(r"<[^<>]*(?:<[^<>]*>[^<>]*)*>\s*$", "", before.rstrip()).rstrip()
        parts = before.rsplit(None, 1)
        name, type_text = (parts[-1], parts[0] if len(parts) == 2 else None)
        return {**base, "name": name, "type": type_text, "params": _params(inner or "")}
    parts = head.strip().rsplit(None, 1)
    if len(parts) != 2:
        return None
    body = rest[stop:]
    return {**base, "name": parts[1], "type": parts[0].strip(), "get": body.startswith("=>") or bool(re.search(r"\bget\b", body))}


def _holder(span: tuple, rows: list, key=lambda r: (r["line"], r["end_line"])) -> dict | None:
    """The smallest row whose line range holds `span`, other than a row that is exactly `span`."""
    best = None
    for r in rows:
        lo, hi = key(r)
        if lo <= span[0] and span[1] <= hi and (lo, hi) != span:
            if best is None or (hi - lo) < (key(best)[1] - key(best)[0]):
                best = r
    return best


def assemble(matches_by_file: dict) -> dict:
    """{path: declarations} from the captures of each file (see `QUERY`)."""
    return {path: _file(ms) for path, ms in sorted(matches_by_file.items())}


def _file(ms: list) -> dict:
    out = {"namespaces": [], "usings": [], "types": [], "top_level": False, "idents": {}, "qualified": [], "assembly_attributes": []}
    ns_rows = []
    for m in ms:
        cap = m["capture"]
        span = (m["start_line"], m["end_line"])
        if cap == "ns":
            found = re.match(r"namespace\s+([\w.]+)", m["text"])
            if found:
                scoped = m["text"].rstrip().endswith(";")  # a file-scoped namespace holds the rest of the file, but its node is only the first line
                ns_rows.append({"name": found.group(1), "line": span[0], "end_line": FILE_END if scoped else span[1]})
        elif cap == "using":
            found = re.match(r"(global\s+)?using\s+(static\s+)?(?:(\w+)\s*=\s*)?([\w.<>,\s?]+?)\s*;", m["text"].strip())
            if found:
                out["usings"].append({"name": found.group(4).strip(), "global": bool(found.group(1)), "static": bool(found.group(2)), "alias": found.group(3)})
        elif cap == "attrlist" and re.match(r"\[\s*assembly\s*:", m["text"]):
            out["assembly_attributes"] += _attributes(m["text"].replace("assembly:", "", 1), m["start_line"])[0]
        elif cap == "global":
            out["top_level"] = True
        elif cap == "ident":
            if m["text"][:1].isupper():
                out["idents"].setdefault(m["text"], []).append(m["start_line"])
        elif cap == "qualified":
            out["qualified"].append(m["text"])
    for row in ns_rows:
        parents = [p for p in ns_rows if p is not row and p["line"] <= row["line"] and row["end_line"] <= p["end_line"] and (p["line"], p["end_line"]) != (row["line"], row["end_line"])]
        row["name"] = ".".join(p["name"] for p in sorted(parents, key=lambda p: p["line"])) + ("." if parents else "") + row["name"]
    out["namespaces"] = sorted(ns_rows, key=lambda r: (r["line"], r["name"]))
    types = [t for t in (_type(m) for m in ms if m["capture"] == "type") if t]
    for t in types:
        outer = _holder((t["line"], t["end_line"]), types)
        t["outer"] = outer["name"] if outer else None
        ns = _holder((t["line"], t["end_line"]), ns_rows, key=lambda r: (r["line"], r["end_line"]))
        if ns is None:
            ns = next((n for n in ns_rows if n["line"] <= t["line"] and t["end_line"] <= n["end_line"]), None)
        t["namespace"] = ns["name"] if ns else ""
        for p in t["params"]:
            t["members"].append({"name": p["name"], "kind": "property", "modifiers": ["public"], "line": t["line"], "end_line": t["line"], "attributes": [],
                                 "type": p["type"], "static": False, "params": [], "get": True})
    for m in ms:
        if not m["capture"].startswith("member."):
            continue
        member = _member(m, m["capture"].split(".", 1)[1])
        holder = _holder((m["start_line"], m["end_line"]), types)
        if member and holder:
            holder["members"].append(member)
    for t in types:
        t["members"].sort(key=lambda r: (r["line"], r["name"]))
    out["types"] = sorted(types, key=lambda t: (t["line"], t["name"]))
    return out


def declarations(ts, files: list) -> dict:
    """{path: declarations} for the `.cs` files in `files`. Every file asked for gets an entry, even an empty one."""
    names = [f for f in files if f.endswith(".cs")]
    by_file: dict = {p: [] for p in names}
    for m in ts.query("csharp", names, QUERY) if names else []:
        by_file.setdefault(m["path"], []).append(m)
    return assemble(by_file)


def complexity(ts, files: list) -> dict:
    """{path: number of branch nodes}. Every `.cs` file asked for gets a number."""
    counts = {p: 0 for p in files if p.endswith(".cs")}
    for m in ts.query("csharp", list(counts), COMPLEXITY_Q) if counts else []:
        if m["path"] in counts:
            counts[m["path"]] += 1
    return counts
