"""What `reading.map` and `conventions.tooling` know about C# repositories (M5-23).

Pure functions of paths and file text, like `measured_js`. `measured.py` calls them next to its other rules, so a tree with no C# gives the same rows as before.
"""
from __future__ import annotations

import re

CONFIG_FILE = re.compile(r"(^|/)(appsettings(\.[^/]+)?\.json|launchSettings\.json|global\.json|nuget\.config|Directory\.(Build\.props|Build\.targets|Packages\.props)"
                         r"|[^/]+\.runsettings|\.config/dotnet-tools\.json)$", re.I)
BUILD_FILE = re.compile(r"(^|/)([^/]+\.(sln|slnx|csproj)|build\.cake)$", re.I)
CSHARPIER_FILE = re.compile(r"(^|/)\.csharpierrc(\.json|\.yaml)?$")
STYLECOP_FILE = re.compile(r"(^|/)stylecop\.json$", re.I)
GLOBALCONFIG_FILE = re.compile(r"(^|/)([^/]*\.)?globalconfig$")
MSBUILD_FILE = re.compile(r"\.(props|csproj|targets)$")
ENFORCE = re.compile(r"<EnforceCodeStyleInBuild>\s*true\s*<", re.I)
# Words that stand for a tool in a CI file, where its own name is not what gets written.
CI_NAMES = {"dotnet-format": r"dotnet[ -]format", "csharpier": r"csharpier", "StyleCop": r"StyleCop", ".globalconfig": r"\.globalconfig"}


def is_config(path: str) -> bool:
    return bool(CONFIG_FILE.search(path))


def is_build(path: str) -> bool:
    return bool(BUILD_FILE.search(path))


def _lines(tree, read, pattern) -> list:
    """(path, line) of the first line of each props or project file whose text matches `pattern`."""
    found = []
    for p in sorted(t for t in tree if MSBUILD_FILE.search(t)):
        text = read(p) or ""
        m = pattern.search(text)
        if m:
            found.append((p, text.count("\n", 0, m.start()) + 1))
    return found


def tool_locations(tree, read, line_of) -> dict:
    """tool -> [(path, line or None)] for the C# tools with a config file or a setting. `line_of` is `measured._line_of`."""
    if read is None:
        return {}
    found: dict = {}
    csharpier = [(p, None) for p in sorted(tree) if CSHARPIER_FILE.search(p)]
    tools = ".config/dotnet-tools.json"
    if tools in tree and re.search(r'"csharpier"', read(tools) or "", re.I):
        csharpier.append((tools, line_of(read(tools) or "", '"csharpier"')))
    if csharpier:
        found["csharpier"] = csharpier
    if any(p.rsplit("/", 1)[-1] == ".editorconfig" for p in tree):
        enforce = _lines(tree, read, ENFORCE)
        if enforce:
            found["dotnet-format"] = enforce
    stylecop = [(p, None) for p in sorted(tree) if STYLECOP_FILE.search(p)] + _lines(tree, read, re.compile(r"StyleCop\.Analyzers"))
    if stylecop:
        found["StyleCop"] = stylecop
    glob = [(p, None) for p in sorted(tree) if GLOBALCONFIG_FILE.search(p)]
    if glob:
        found[".globalconfig"] = glob
    return found
