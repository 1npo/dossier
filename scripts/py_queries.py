"""Tree-sitter queries for Python: models, tests, module-level state and imports.

The worker returns flat captures (path, capture name, lines, columns, text). Each `assemble_*` function pairs them up
by position, so the pairing logic is pure and tested with hand-made capture lists.
"""
from __future__ import annotations

import re

# Three-level patterns (module > statement > assignment) match nothing in this grammar version, so every query is one
# or two levels deep and the code tells module level and class level apart by column: a module-level name starts at
# column 0, and a class field starts at the column of the class body block.
CLASS_Q = ("(class_definition name: (identifier) @class.name superclasses: (argument_list)? @class.bases "
           "body: (block) @class.body) @class")
DECORATOR_Q = "(decorated_definition definition: (class_definition)) @decorated"
FIELD_Q = "(assignment left: (identifier) @field.name type: (_)? @field.type right: (_)? @field.value)"
IMPORT_Q = "(import_statement) @import.stmt\n(import_from_statement) @import.from"
MODULE_ASSIGN_Q = ("(assignment left: (identifier) @state.name right: "
                   "[(dictionary) (list) (set) (dictionary_comprehension) (list_comprehension) (set_comprehension)] @state.value)")
TEST_Q = ("(function_definition name: (identifier) @func.name)\n"
          "(class_definition name: (identifier) @class.name superclasses: (argument_list)? @class.bases)\n"
          "(decorator) @decorator\n(call function: (_) @call.fn)\n" + IMPORT_Q)

ENUM_BASES = {"Enum", "IntEnum", "StrEnum", "Flag", "IntFlag"}
ATTRS_DECOS = {"attrs.define", "attr.s", "define", "attr.define", "attrs.frozen", "attr.attrs", "attrs.mutable"}
PLAIN_FIELD_KINDS = {"enum", "sqlalchemy", "django"}
MOCK_RE = re.compile(r"(^|\.)(patch|MagicMock|Mock|AsyncMock)$|^mock\.|^monkeypatch\.")
TEST_NAME_RE = re.compile(r"^test(_|[A-Z0-9])")


def _tail(name: str) -> str:
    return name.rsplit(".", 1)[-1]


def split_bases(text: str) -> list:
    """['Base', 'mixins.A'] from '(Base, mixins.A, metaclass=M)': top-level commas only, keyword arguments dropped."""
    parts, depth, cur = [], 0, ""
    for ch in text.strip()[1:-1]:
        depth += ch in "([{"
        depth -= ch in ")]}"
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts if p.strip() and "=" not in p.split("[")[0]]


def _same_line(items, anchor, after_col):
    return next((m for m in items if m["path"] == anchor["path"] and m["start_line"] == anchor["start_line"]
                 and m["start_col"] > after_col), None)


def _classes(matches: list) -> list:
    names = [m for m in matches if m["capture"] == "class.name"]
    bases = [m for m in matches if m["capture"] == "class.bases"]
    bodies = [m for m in matches if m["capture"] == "class.body"]
    out = []
    for c in (m for m in matches if m["capture"] == "class"):
        name = _same_line(names, c, c["start_col"])
        if name is None:
            continue
        b = _same_line(bases, c, name["start_col"])
        body = min((x for x in bodies if x["path"] == c["path"] and x["start_line"] >= c["start_line"] and x["end_line"] == c["end_line"]),
                   key=lambda x: x["start_line"], default=None)
        out.append({"path": c["path"], "name": name["text"], "line": c["start_line"], "end_line": c["end_line"],
                    "body": (body["start_line"], body["start_col"]) if body else None,
                    "snippet": c["text"].splitlines()[0].strip(), "bases": split_bases(b["text"]) if b else []})
    return sorted(out, key=lambda c: (c["path"], c["line"]))


def _decorators(decorated: list) -> dict:
    """(path, class line) -> decorator names, from the text of each decorated class."""
    found = {}
    for d in decorated:
        lines, decos, i = d["text"].splitlines(), [], 0
        while i < len(lines) and not re.match(r"\s*class\s", lines[i]):
            if lines[i].lstrip().startswith("@"):
                decos.append(lines[i].lstrip()[1:].split("(")[0].strip())
            i += 1
        found[(d["path"], d["start_line"] + i)] = decos
    return found


def _kind(bases: list, decos: list, field_names: set, known: dict) -> str | None:
    tails = {_tail(b.split("[")[0]) for b in bases}
    if tails & ENUM_BASES:
        return "enum"
    for kind, names in (("typeddict", {"TypedDict"}), ("namedtuple", {"NamedTuple"}),
                        ("pydantic", {"BaseModel", "BaseSettings"})):
        if tails & names:
            return kind
    if any(re.match(r"^models\.\w*Model$", b) for b in bases):
        return "django"
    if tails & {"Base", "DeclarativeBase"} or "__tablename__" in field_names:
        return "sqlalchemy"
    if any(_tail(d) == "dataclass" for d in decos):
        return "dataclass"
    if any(d in ATTRS_DECOS for d in decos):
        return "attrs"
    return next((known[t] for t in tails if t in known), None)


def _ref(type_text, value_text, names: set, own: str):
    m = re.search(r"(?:ForeignKey|relationship)\(\s*[\"']?(\w+)", value_text or "")
    if m:
        return m.group(1)
    return next((w for w in re.findall(r"[A-Za-z_]\w*", type_text or "") if w in names and w != own), None)


def assemble_models(class_matches: list, field_matches: list, decorator_matches: list) -> list:
    classes, decos = _classes(class_matches), _decorators(decorator_matches)
    field_names = [m for m in field_matches if m["capture"] == "field.name"]
    types = [m for m in field_matches if m["capture"] == "field.type"]
    values = [m for m in field_matches if m["capture"] == "field.value"]
    for c in classes:
        c["raw"] = []
        for f in field_names:
            if (f["path"] == c["path"] and c["body"] and f["start_col"] == c["body"][1]
                    and c["body"][0] <= f["start_line"] <= c["end_line"]):
                t, v = _same_line(types, f, f["start_col"]), _same_line(values, f, f["start_col"])
                c["raw"].append({"name": f["text"], "line": f["start_line"], "type": t["text"] if t else None,
                                 "value": v["text"] if v else None})
    known: dict = {}
    for _ in range(2):  # a second pass lets a subclass of a model be a model of the same kind
        for c in classes:
            kind = _kind(c["bases"], decos.get((c["path"], c["line"]), []), {f["name"] for f in c["raw"]}, known)
            if kind:
                known[c["name"]] = kind
    models = [c for c in classes if c["name"] in known]
    names = {c["name"] for c in models}
    items = []
    for c in models:
        kind = known[c["name"]]
        fields = [{"name": f["name"], "type": f["type"], "line": f["line"], "ref": _ref(f["type"], f["value"], names, c["name"])}
                  for f in c["raw"] if not f["name"].startswith("__") and (f["type"] or kind in PLAIN_FIELD_KINDS)]
        items.append({"path": c["path"], "line": c["line"], "end_line": c["end_line"], "name": c["name"], "kind": kind,
                      "rule": kind, "snippet": c["snippet"], "bases": c["bases"], "fields": fields})
    return items


def migrations(files: list) -> list:
    items = []
    for p in files:
        if re.search(r"(^|/)alembic/versions/[^/]+\.py$|(^|/)versions/[^/_][^/]*\.py$", p):
            items.append({"path": p, "kind": "migration", "tool": "alembic", "rule": "migration"})
        elif re.search(r"(^|/)migrations/\d[^/]*\.py$", p):
            items.append({"path": p, "kind": "migration", "tool": "django", "rule": "migration"})
    return items


def models(ts, files: list) -> list:
    if not files:
        return []
    return assemble_models(ts.query("python", files, CLASS_Q), ts.query("python", files, FIELD_Q),
                           ts.query("python", files, DECORATOR_Q)) + migrations(files)


def assemble_state(matches: list) -> list:
    """Module-level dict, list and set values. An all-capitals name with a filled value is a constant and is skipped;
    an empty one (`CART = {}`) is almost certainly filled in later, so it stays."""
    names = [m for m in matches if m["capture"] == "state.name"]
    items = []
    for v in (m for m in matches if m["capture"] == "state.value"):
        n = next((x for x in names if x["path"] == v["path"] and x["start_line"] == v["start_line"] and x["start_col"] == 0), None)
        constant = n is not None and n["text"] == n["text"].upper() and v["text"].replace(" ", "") not in ("{}", "[]")
        if n is None or constant:
            continue
        items.append({"path": v["path"], "line": v["start_line"], "end_line": v["end_line"], "category": "global-state",
                      "rule": "dossier.python.state.module-mutable", "name": n["text"],
                      "snippet": (n["text"] + " = " + v["text"].splitlines()[0].strip())[:200], "detail": n["text"]})
    return sorted(items, key=lambda i: (i["path"], i["line"]))


def module_state(ts, files: list) -> list:
    return assemble_state(ts.query("python", files, MODULE_ASSIGN_Q)) if files else []


def parse_import(text: str, importer: str, is_package: bool = False) -> list:
    """[(module, [names])] for one import statement. Relative imports are resolved against the importing module."""
    text = " ".join(text.replace("(", " ").replace(")", " ").replace("\\", " ").split())
    if text.startswith("import "):
        return [(part.split(" as ")[0].strip(), []) for part in text[7:].split(",") if part.strip()]
    m = re.match(r"from\s+(\.*)([\w.]*)\s+import\s+(.+)$", text)
    if not m:
        return []
    dots, mod, names = len(m.group(1)), m.group(2), [n.split(" as ")[0].strip() for n in m.group(3).split(",") if n.strip()]
    if dots:
        pkg = importer.split(".") if is_package else importer.split(".")[:-1]
        pkg = pkg[: len(pkg) - (dots - 1)] if dots > 1 else pkg
        mod = ".".join(pkg + ([mod] if mod else []))
    return [(mod, names)]


def resolve(targets: list, module_paths: dict) -> list:
    """The project modules an import statement refers to (sorted, without duplicates)."""
    found = set()
    for mod, names in targets:
        hits = [f"{mod}.{n}" if mod else n for n in names if (f"{mod}.{n}" if mod else n) in module_paths]
        if hits:
            found |= set(hits)
            continue
        parts = mod.split(".")
        for i in range(len(parts), 0, -1):
            if ".".join(parts[:i]) in module_paths:
                found.add(".".join(parts[:i]))
                break
    return sorted(found)


def assemble_imports(matches: list, module_paths: dict) -> list:
    by_path = {p: m for m, p in module_paths.items()}
    edges: dict = {}
    for m in matches:
        if m["capture"] not in ("import.stmt", "import.from"):
            continue
        importer = by_path.get(m["path"]) or m["path"][:-3].replace("/", ".")
        is_package = m["path"].endswith("/__init__.py")
        for target in resolve(parse_import(m["text"], importer, is_package), module_paths):
            if target != importer:
                edges.setdefault((m["path"], importer, target), set()).add(m["start_line"])
    return [{"kind": "import", "path": path, "paths": [module_paths[to]], "from": frm, "to": to, "lines": sorted(lines),
             "via": "tree-sitter"} for (path, frm, to), lines in sorted(edges.items())]


def imports(ts, files: list, module_paths: dict) -> list:
    return assemble_imports(ts.query("python", files, IMPORT_Q), module_paths) if files else []


def assemble_tests(matches_by_file: dict, module_paths: dict) -> list:
    items = []
    for path, ms in sorted(matches_by_file.items()):
        def texts(cap):
            return [m["text"] for m in ms if m["capture"] == cap]

        segs = set(path.split("/")[:-1])
        decorators = [d.lower() for d in texts("decorator")]
        mods = resolve([t for m in ms if m["capture"] in ("import.stmt", "import.from")
                        for t in parse_import(m["text"], path[:-3].replace("/", "."))], module_paths)
        items.append({
            "kind": "test-file", "path": path,
            "test_kind": "e2e" if "e2e" in segs else "integration" if segs & {"integration", "functional", "live"} else "unit",
            "framework": "unittest" if any("TestCase" in b for b in texts("class.bases")) else "pytest",
            "tests": sum(bool(TEST_NAME_RE.match(n)) for n in texts("func.name")),
            "classes": sum(n.startswith("Test") for n in texts("class.name")),
            "skips": sum("skip" in d for d in decorators), "xfails": sum("xfail" in d for d in decorators),
            "mocks": sum(bool(MOCK_RE.search(c)) for c in texts("call.fn")),
            "fixtures": sum("fixture" in d for d in decorators),
            "imports": mods, "paths": sorted({module_paths[m] for m in mods})})
    return items


def tests(ts, test_files: list, module_paths: dict) -> list:
    if not test_files:
        return []
    by_file: dict = {p: [] for p in test_files}
    for m in ts.query("python", test_files, TEST_Q):
        by_file.setdefault(m["path"], []).append(m)
    return assemble_tests(by_file, module_paths)
