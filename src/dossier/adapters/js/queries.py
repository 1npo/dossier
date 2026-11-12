"""Tree-sitter queries for JavaScript and TypeScript: tests, complexity and module-level state (plan 010, D8).

The worker returns flat captures (path, capture name, lines, columns, text). The `assemble_*` functions pair them up, so the
logic is pure and tested with hand-made capture lists. Patterns stay one or two levels deep. Configuration files are code,
so they are read as text with regular expressions and never run.
"""
from __future__ import annotations

import posixpath
import re

GRAMMARS = {".ts": "typescript", ".mts": "typescript", ".cts": "typescript", ".tsx": "tsx",
            ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript"}
CALL_Q = "(call_expression function: (_) @call.fn)"
IMPORT_Q = "(import_statement source: (string) @import.source)"
COMPLEXITY_Q = ("[(if_statement) (for_statement) (for_in_statement) (while_statement) (do_statement) (switch_case) (catch_clause) "
                "(ternary_expression) (binary_expression operator: [\"&&\" \"||\" \"??\"])] @branch")
DECLARATION_Q = "(lexical_declaration) @decl"
EXPORTED_DECLARATION_Q = "(export_statement declaration: (lexical_declaration) @decl)"

PLAIN_NAME = re.compile(r"^[\w$]+(\.[\w$]+)*$")
TEST_HEADS, SUITE_HEADS = {"it", "test", "specify"}, {"describe", "suite"}
TEST_TAILS = {"each", "only", "concurrent"}
SKIPS = {"skip", "todo", "fixme"}
OLD_SKIPS = {"xit", "xtest", "xdescribe"}
XFAILS = {"failing", "fails"}
MOCKS = {"jest.mock", "jest.fn", "jest.spyOn", "vi.mock", "vi.fn", "vi.spyOn", "setupServer", "mockDeep"}
HOOKS = {"beforeAll", "beforeEach", "afterAll", "afterEach"}
FRAMEWORK_IMPORTS = {"@playwright/test": "playwright", "vitest": "vitest", "node:test": "node:test"}


def by_grammar(files: list) -> dict:
    """{grammar name: [files]} for the files the three grammars read; other extensions are left out."""
    out: dict = {}
    for f in files:
        g = GRAMMARS.get(posixpath.splitext(f)[1])
        if g:
            out.setdefault(g, []).append(f)
    return out


def _query_all(ts, files: list, query: str) -> list:
    found = []
    for grammar, group in by_grammar(files).items():
        found += ts.query(grammar, group, query)
    return found


def _classify(fn: str) -> set:
    """Which counters a call named `fn` feeds."""
    parts = fn.split(".")
    head, rest = parts[0], parts[1:]
    kinds = set()
    if fn in MOCKS or head == "sinon":
        kinds.add("mocks")
    if head in HOOKS or fn == "test.extend" or (head == "test" and rest and rest[-1] in HOOKS):
        kinds.add("fixtures")
    if head in OLD_SKIPS or (rest and SKIPS & set(rest)):
        kinds.add("skips")
    if XFAILS & set(rest):
        kinds.add("xfails")
    if "skips" in kinds:
        return kinds
    if head in TEST_HEADS and set(rest) <= TEST_TAILS:
        kinds.add("tests")
    elif head in SUITE_HEADS and set(rest) <= TEST_TAILS | {"serial", "parallel"}:
        kinds.add("classes")
    elif head == "test" and rest[:1] == ["describe"]:
        kinds.add("classes")
    return kinds


def assemble_tests(matches_by_file: dict, runner_of) -> list:
    """`test-file` items from the captures of each file. `runner_of(path)` names the project's runner from its configuration, or None."""
    items = []
    for path, ms in sorted(matches_by_file.items()):
        counts = {k: 0 for k in ("tests", "classes", "skips", "xfails", "mocks", "fixtures")}
        for m in ms:
            if m["capture"] == "call.fn" and PLAIN_NAME.match(m["text"]):
                for k in _classify(m["text"]):
                    counts[k] += 1
        sources = {m["text"].strip("'\"`") for m in ms if m["capture"] == "import.source"}
        framework = next((FRAMEWORK_IMPORTS[s] for s in sorted(sources) if s in FRAMEWORK_IMPORTS), None)
        if framework is None and (path.startswith("cypress/") or "/cypress/" in path):
            framework = "cypress"
        framework = framework or runner_of(path) or "unknown"
        segs = set(path.split("/")[:-1])
        kind = "e2e" if "e2e" in segs or framework in ("playwright", "cypress") else "integration" if segs & {"integration", "functional", "live"} else "unit"
        items.append({"kind": "test-file", "path": path, "test_kind": kind, "framework": framework, **counts, "imports": [], "paths": []})
    return items


def tests(ts, files: list, runner_of) -> list:
    if not files:
        return []
    by_file: dict = {p: [] for p in files if posixpath.splitext(p)[1] in GRAMMARS}
    for query in (CALL_Q, IMPORT_Q):
        for m in _query_all(ts, list(by_file), query):
            by_file.setdefault(m["path"], []).append(m)
    return assemble_tests(by_file, runner_of)


def complexity(ts, files: list) -> dict:
    """{path: number of branch nodes}. Every file asked for gets a number."""
    counts = {p: 0 for p in files}
    for m in _query_all(ts, files, COMPLEXITY_Q):
        if m["path"] in counts:
            counts[m["path"]] += 1
    return counts


DECL = re.compile(r"^(let|const)\s+([\w$]+)\s*(?::[^=]+)?(?:=\s*(.*))?$", re.S)


def assemble_state(matches: list) -> list:
    """Module-level `let`, and `const` set to an empty object, an empty array, or a Map, Set or WeakMap. An all-capitals name with a filled value is a constant."""
    items = []
    for m in matches:
        if m["capture"] != "decl" or m["start_col"] not in (0, 7):
            continue
        found = DECL.match(m["text"].strip().rstrip(";"))
        if not found:
            continue
        keyword, name, value = found.group(1), found.group(2), (found.group(3) or "").strip()
        compact = value.replace(" ", "")
        empty = compact in ("{}", "[]", "newMap()", "newSet()", "newWeakMap()")
        if keyword == "const" and not (empty or re.match(r"new(Map|Set|WeakMap)\b", compact)):
            continue
        if keyword == "const" and name == name.upper() and not empty:
            continue
        items.append({"path": m["path"], "line": m["start_line"], "end_line": m["end_line"], "category": "global-state",
                      "rule": "dossier.js.state.module-mutable", "name": name,
                      "snippet": m["text"].splitlines()[0].strip()[:200], "detail": name})
    return sorted(items, key=lambda i: (i["path"], i["line"]))


def module_state(ts, files: list) -> list:
    matches = [m for m in _query_all(ts, files, DECLARATION_Q) if m["start_col"] == 0]
    matches += [m for m in _query_all(ts, files, EXPORTED_DECLARATION_Q) if m["start_col"] == 7]
    return assemble_state(matches)


# ---- configuration files, read as text -------------------------------------------------------------------------------

CONFIGS = ((re.compile(r"^jest\.config\.\w+$"), "jest"), (re.compile(r"^vitest\.config\.\w+$"), "vitest"), (re.compile(r"^\.mocharc(\.\w+)?$"), "mocha"),
           (re.compile(r"^playwright\.config\.\w+$"), "playwright"), (re.compile(r"^cypress\.config\.\w+$"), "cypress"),
           (re.compile(r"^\.c8rc(\.\w+)?$"), "c8"), (re.compile(r"^\.nycrc(\.\w+)?$"), "nyc"))
RUNNERS = ("vitest", "jest", "mocha")
THRESHOLD = re.compile(r"(?:statements|branches|functions|lines)['\"]?\s*:\s*(\d+)")
MATCH = re.compile(r"(testMatch|testRegex|include)['\"]?\s*:\s*(\[[^\]]*\]|'[^']*'|\"[^\"]*\"|`[^`]*`)")


def _settings(text: str, tool: str) -> dict:
    out = {}
    anchor = text.find("coverageThreshold") if tool == "jest" else text.find("thresholds") if tool == "vitest" else 0
    if anchor >= 0 and tool != "mocha":
        numbers = [int(n) for n in THRESHOLD.findall(text[anchor:anchor + 600])]
        if numbers:
            out["coverage_threshold"] = min(numbers)
    found = MATCH.search(text) if tool in ("jest", "vitest") else None
    if found:
        out["test_match"] = " ".join(found.group(2).split())
    return out


def test_configs(tree, read) -> list:
    """`config` items for the JavaScript test tools: one per configuration file, plus `jest` in package.json and a `test:` block in vite.config."""
    items = []
    for path in sorted(tree):
        base = posixpath.basename(path)
        if "node_modules/" in path:
            continue
        for pattern, tool in CONFIGS:
            if pattern.match(base):
                items.append({"kind": "config", "path": path, "tool": tool, "settings": _settings(read(path) or "", tool)})
        if re.match(r"^vite\.config\.\w+$", base):
            text = read(path) or ""
            if re.search(r"\btest\s*:\s*\{", text):
                items.append({"kind": "config", "path": path, "tool": "vitest", "settings": _settings(text, "vitest")})
        elif base == "package.json":
            text = read(path) or ""
            if re.search(r"\"jest\"\s*:\s*\{", text):
                items.append({"kind": "config", "path": path, "tool": "jest", "settings": _settings(text, "jest")})
    return sorted(items, key=lambda i: (i["path"], i["tool"]))


def runner_of(configs: list):
    """A function from a test file's path to the runner configured in the nearest folder above it (vitest, then jest, then mocha)."""
    folders: dict = {}
    for c in configs:
        if c["tool"] in RUNNERS:
            folders.setdefault(posixpath.dirname(c["path"]), set()).add(c["tool"])

    def find(path: str):
        folder = posixpath.dirname(path)
        while True:
            if folder in folders:
                return next(r for r in RUNNERS if r in folders[folder])
            if not folder:
                return None
            folder = posixpath.dirname(folder)
    return find
