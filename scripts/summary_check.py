"""V8: a small validator for `summary.json`, covering exactly the JSON Schema keywords `prompts/summary.schema.json` uses.

A schema keyword that is not handled here raises, so the schema file and this code cannot drift apart silently.
"""
from __future__ import annotations

import json
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "prompts" / "summary.schema.json"
CONSTRAINTS = {"type", "required", "properties", "additionalProperties", "items", "enum", "minimum"}
ANNOTATIONS = {"$schema", "title", "description"}
TYPES = {"object": dict, "array": list, "string": str, "null": type(None), "boolean": bool}


def load_schema(path=SCHEMA_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _is(value, name) -> bool:
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, TYPES[name]) and not (name != "boolean" and isinstance(value, bool))


def _check(value, schema, where, out) -> None:
    unknown = set(schema) - CONSTRAINTS - ANNOTATIONS
    if unknown:
        raise ValueError(f"summary.schema.json uses {', '.join(sorted(unknown))} at {where}, which summary_check does not implement.")
    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is(value, n) for n in names):
            out.append(f"V8: summary.json: {where}: must be {' or '.join(names)}.")
            return
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"V8: summary.json: {where}: must be one of {', '.join(str(v) for v in schema['enum'])}, found {value!r}.")
    if "minimum" in schema and isinstance(value, (int, float)) and not isinstance(value, bool) and value < schema["minimum"]:
        out.append(f"V8: summary.json: {where}: must be at least {schema['minimum']}.")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                out.append(f"V8: summary.json: {where}: the key {key} is missing.")
        props = schema.get("properties", {})
        for key, sub in value.items():
            if key in props:
                _check(sub, props[key], f"{where}.{key}", out)
            elif schema.get("additionalProperties") is False:
                out.append(f"V8: summary.json: {where}: the key {key} is not allowed.")
    if isinstance(value, list) and "items" in schema:
        for n, item in enumerate(value):
            _check(item, schema["items"], f"{where}[{n}]", out)


def validate(doc, schema=None) -> list:
    """Problems of `doc` against the schema, one line each. `$` stands for the whole document."""
    out: list = []
    _check(doc, schema if schema is not None else load_schema(), "$", out)
    return out
