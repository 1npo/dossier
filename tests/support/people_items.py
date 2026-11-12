"""Made-up `extract/history.json` items for the people figures and the contributors cards."""


def file_item(path, authors=None, blame=None, owner_lines=None):
    return {"kind": "file", "path": path, "authors": authors or {}, "blame": blame, "owner_lines": owner_lines}


CATALOG = [{"name": "Core", "paths": ["src/core/"]}, {"name": "Web", "paths": ["src/web/"]}]


def person(ident, name, kind="human", commits=1, owned_lines=0, aliases=()):
    return {"kind": "person", "person": ident, "name": name, "type": kind, "commits": commits, "owned_lines": owned_lines, "aliases": list(aliases)}


META = {"kind": "meta", "status": "ok"}


def humans(*lines):
    return {"extract": {"history": [META] + [person(f"h{i}", f"H{i}", owned_lines=n) for i, n in enumerate(lines)]}}
