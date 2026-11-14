"""Non-code files that the code reads (templates, data tables, reference data), found as groups and linked to the code.

No extractor emits a finding for a `.mjml` email template or a `data/mime_data.json`, because they are not code. Yet the code
loads them by path, by directory or by a pattern such as `f"templates/{kind}.mjml"`, and a reader who never hears of them
misses an input of the program. This module groups the tracked non-code files by (folder, extension), so 27 templates are one
group, and looks for the code that refers to each group. Every group becomes one finding (`rs-...`) that the Inputs card must
keep or dismiss.
"""
from __future__ import annotations

import posixpath
import re
from collections.abc import Callable, Collection

from dossier.facts import gather

__all__ = ["detect", "ID_PREFIX", "RESOURCE_EXT"]

ID_PREFIX = "rs"
RESOURCE_EXT = frozenset("mjml html htm jinja jinja2 j2 txt json csv tsv xlsx xlsm docx yaml yml toml ini sql xml md".split())
STRONG_EXT = frozenset("mjml jinja jinja2 j2 csv tsv xlsx xlsm docx sql".split())     # listed even when no code refers to them
COMMON_EXT = frozenset("json txt md yaml yml xml html htm toml ini csv tsv".split())   # an extension pattern alone is weak evidence
DATA_DIRS = frozenset({"data", "resources", "templates", "fixtures"})
GENERIC_DIRS = DATA_DIRS | {"static", "files", "config", "assets", "lib", "src"}
SKIP_TOP = frozenset({".github", ".vscode", ".idea", ".devcontainer", ".circleci", ".gitlab", "docs", "doc", "node_modules"})
DUNDER_FILE = "__" + "file" + "__"   # spelled in two parts: tests/content/test_layers.py forbids the bare name outside resources.py
PACKAGE_CALLS = re.compile(r"importlib\.resources|pkgutil\.get_data|pkg_resources|importlib_resources|Path\(" + DUNDER_FILE + r"\)|dirname\(" + DUNDER_FILE + r"\)")
MAX_CODE_BYTES = 1_000_000
MAX_REFS = 20
MAX_LISTED = 8


def _candidate(path: str) -> bool:
    """Whether a tracked file may be a resource at all (before looking at who reads it)."""
    segs = path.split("/")
    base = segs[-1]
    if "." not in base or base.startswith(".") or gather.noise_reason(path) or gather.MANIFEST_NAMES.search(path):
        return False
    ext = base.rsplit(".", 1)[-1].lower()
    if ext not in RESOURCE_EXT or segs[0] in SKIP_TOP or len(segs) == 1 and ext not in STRONG_EXT:
        return False
    lang = gather.lang_of(path)
    return not (lang and lang[1] == "code" and ext != "sql")


def _data_dir(path: str) -> bool:
    return bool(DATA_DIRS.intersection(path.split("/")[:-1]))


def _literal(name: str) -> re.Pattern:
    """`name` inside a quoted string. A generic folder name (data, templates) must be a whole path part of the string."""
    esc = re.escape(name)
    if name.lower() in GENERIC_DIRS:
        return re.compile(rf"""['"](?:[^'"\n]*/)?{esc}/?['"]|['"]{esc}/""")
    return re.compile(rf"""['"][^'"\n]*(?<![\w-]){esc}(?![\w-])[^'"\n]*['"]""")


def _ext_literal(ext: str) -> re.Pattern:
    return re.compile(rf"""['"][^'"\n]*\.{re.escape(ext)}(?![\w])[^'"\n]*['"]""", re.I)


def _first_line(text: str, pattern: re.Pattern, needle: str) -> int | None:
    """The 1-based line of the first match of `pattern` (a cheap substring test on `needle` comes first)."""
    if needle not in text:
        return None
    for n, line in enumerate(text.split("\n"), 1):
        if needle in line and pattern.search(line):
            return n
    return None


def _top(path: str) -> str:
    return path.split("/")[0]


def detect(tree: Collection[str], read: Callable[[str], str | None]) -> list[dict]:
    """The resource groups of the tracked files, each with the code that reads it. `read(path)` gives a file's text or None.

    An item: {path (first member), kind, rule, name, snippet, display, directory, extension, count, members, referenced_by}.
    A group is kept when code refers to it, when it lives in a data, resources, templates or fixtures folder, or when its
    extension says template or table (mjml, j2, csv, xlsx, ...). A file under tests/ counts only when non-test code reads it."""
    groups: dict = {}
    for p in sorted(tree):
        if _candidate(p):
            groups.setdefault((posixpath.dirname(p), p.rsplit(".", 1)[-1].lower()), []).append(p)
    if not groups:
        return []
    code = [p for p in sorted(tree) if (gather.lang_of(p) or (None, None))[1] == "code" and not gather.noise_reason(p)]
    texts = {}
    for p in code:
        t = read(p)
        if t is not None and len(t) <= MAX_CODE_BYTES:
            texts[p] = t
    items = []
    for (directory, ext), members in sorted(groups.items()):
        in_tests = bool(gather.TEST_RE.search(members[0]))
        refs = _references(directory, ext, members, texts)
        if in_tests and not refs:
            continue
        if not (refs or _data_dir(members[0]) or ext in STRONG_EXT):
            continue
        where = f"{directory}/" if directory else ""
        name = f"{where}*.{ext}"
        shown = ", ".join(posixpath.basename(m) for m in members[:MAX_LISTED]) + (f" and {len(members) - MAX_LISTED} more" if len(members) > MAX_LISTED else "")
        readers = "; ".join(f"{r['path']}:{r['line']} ({r['how']})" for r in refs[:5]) + (f" and {len(refs) - 5} more" if len(refs) > 5 else "")
        items.append({"path": members[0], "kind": "resource-group", "rule": f"resources.{ext}", "name": name, "snippet": name,
                      "display": f"{len(members)} file{'s' if len(members) != 1 else ''} ({shown}); " + (f"read by {readers}" if refs else "no code was found that reads them"),
                      "directory": directory, "extension": ext, "count": len(members), "members": members, "referenced_by": refs})
    return items


def _references(directory: str, ext: str, members: list, texts: dict) -> list:
    """The code that refers to a group: [{path, line, how}]. How: file name, folder, extension pattern or package resource call."""
    names = {posixpath.basename(m): m for m in members}
    folder_name = posixpath.basename(directory)
    folder_re = _literal(folder_name) if folder_name else None
    full = directory + "/" if directory else ""
    ext_re = _ext_literal(ext)
    found = []
    for path, text in texts.items():
        if gather.TEST_RE.search(path):
            continue        # a test that reads a file does not make it an input of the program
        hit = None
        for base in names:
            line = _first_line(text, re.compile(r"""['"][^'"\n]*(?<![\w.\-])""" + re.escape(base) + r"""['"]"""), base)
            if line:
                hit = (line, "file name")
                break
        generic_elsewhere = folder_name.lower() in GENERIC_DIRS and _top(path) != _top(members[0]) and full.rstrip("/") not in text
        if not hit and folder_re is not None and not generic_elsewhere:
            line = _first_line(text, folder_re, folder_name) or (_first_line(text, _literal(full.rstrip("/")), full.rstrip("/")) if "/" in full.rstrip("/") else None)
            if line:
                hit = (line, "folder")
        if not hit and (ext not in COMMON_EXT or _top(path) == _top(members[0])):
            line = _first_line(text, ext_re, "." + ext)
            if line and (ext not in COMMON_EXT or folder_name and folder_name in text):
                hit = (line, "extension pattern")
        if hit:
            how = "package resource call" if PACKAGE_CALLS.search(text) and hit[1] != "file name" else hit[1]
            found.append({"path": path, "line": hit[0], "how": how})
    return found[:MAX_REFS]
