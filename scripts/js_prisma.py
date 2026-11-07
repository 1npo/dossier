"""A small parser for Prisma schema files (plan 010, D7). Pure: it takes the path and the text and runs nothing.

It reads `model`, `enum` and `datasource` blocks. A model field gives {name, type, line, ref, pk}; `ref` names another model or enum.
`env("X")` gives an `env-var` finding, and each `datasource` block a `db-connect` finding.
"""
from __future__ import annotations

import re

BLOCK = re.compile(r"^\s*(model|enum|datasource|generator|type|view)\s+(\w+)\s*\{")
FIELD = re.compile(r"^\s*(\w+)\s+(\w+(?:\[\])?\??)(.*)$")
ENUM_MEMBER = re.compile(r"^\s*(\w+)\b")
ENV = re.compile(r"""env\(\s*["']([^"']+)["']\s*\)""")
COMPOSITE_ID = re.compile(r"@@id\(\s*\[([^\]]*)\]")
PROVIDER = re.compile(r"""provider\s*=\s*["']([^"']+)["']""")


def _strip(line: str) -> str:
    return line.split("//", 1)[0].rstrip()


def _blocks(text: str) -> list:
    blocks, current = [], None
    for n, raw in enumerate(text.splitlines(), 1):
        line = _strip(raw)
        if current is None:
            found = BLOCK.match(line)
            if found:
                current = {"keyword": found.group(1), "name": found.group(2), "line": n, "body": [], "head": raw.strip()}
                if line.rstrip().endswith("}"):
                    current["end_line"] = n
                    blocks.append(current)
                    current = None
        elif line.strip().startswith("}"):
            current["end_line"] = n
            blocks.append(current)
            current = None
        else:
            current["body"].append((n, raw, line))
    return blocks


def _model_fields(block: dict, known: set) -> list:
    fields, composite = [], set()
    for n, raw, line in block["body"]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("@@"):
            found = COMPOSITE_ID.search(stripped)
            if found:
                composite |= {p.strip() for p in found.group(1).split(",")}
            continue
        found = FIELD.match(line)
        if not found:
            continue
        name, type_text, rest = found.groups()
        base = type_text.rstrip("?").removesuffix("[]")
        fields.append({"name": name, "type": type_text, "line": n, "ref": base if base in known else None,
                       "pk": bool(re.search(r"@id\b", rest))})
    for f in fields:
        if f["name"] in composite:
            f["pk"] = True
    return fields


def _enum_fields(block: dict) -> list:
    return [{"name": m.group(1), "type": None, "line": n, "ref": None} for n, raw, line in block["body"]
            if line.strip() and not line.strip().startswith("@@") and (m := ENUM_MEMBER.match(line))]


def parse(path: str, text: str) -> dict:
    """{"models": [model items], "io": [env-var and db-connect findings]}."""
    blocks = _blocks(text)
    known = {b["name"] for b in blocks if b["keyword"] in ("model", "enum", "type", "view")}
    models, io = [], []
    for b in blocks:
        if b["keyword"] in ("model", "view", "type"):
            models.append({"path": path, "line": b["line"], "end_line": b["end_line"], "name": b["name"], "kind": "prisma", "rule": "prisma",
                           "snippet": b["head"], "bases": [], "fields": _model_fields(b, known)})
        elif b["keyword"] == "enum":
            models.append({"path": path, "line": b["line"], "end_line": b["end_line"], "name": b["name"], "kind": "prisma-enum", "rule": "prisma-enum",
                           "snippet": b["head"], "bases": [], "fields": _enum_fields(b)})
        if b["keyword"] == "datasource":
            provider = next((m.group(1) for _, _, l in b["body"] if (m := PROVIDER.search(l))), "")
            io.append({"path": path, "line": b["line"], "end_line": b["end_line"], "category": "db-connect", "rule": "js.prisma.datasource",
                       "name": b["name"], "snippet": b["head"], "detail": provider})
        for n, raw, line in b["body"]:
            for m in ENV.finditer(line):
                io.append({"path": path, "line": n, "end_line": n, "category": "env-var", "rule": "js.prisma.env-var", "name": m.group(1),
                           "snippet": raw.strip()[:200], "detail": m.group(1)})
    return {"models": models, "io": io}
