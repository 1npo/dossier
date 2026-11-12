"""C# tests, test configuration and static state, from declarations and project files (plan 011, D14). Pure.

Counts come from attributes on methods and classes, so they need no .NET SDK. Mocks are counted in the file's text.
"""
from __future__ import annotations

import posixpath
import re

FRAMEWORKS = (("xunit", ("xunit", "xunit.v3")), ("nunit", ("nunit",)), ("mstest", ("mstest.testframework", "mstest", "mstest.sdk")), ("tunit", ("tunit",)))
TEST_ATTRS = {"Fact", "Theory", "Test", "TestCase", "TestCaseSource", "TestMethod", "DataTestMethod"}
CLASS_ATTRS = {"TestFixture", "TestClass"}
SKIP_ATTRS = {"Ignore", "Explicit"}
FIXTURE_BASES = ("IClassFixture<", "ICollectionFixture<", "IAsyncLifetime", "WebApplicationFactory<")
FIXTURE_ATTRS = {"SetUp", "OneTimeSetUp", "TearDown", "TestInitialize", "ClassInitialize"}
MOCK_RE = re.compile(r"new Mock<|\bMock\.Of<|\bSubstitute\.For<|\bA\.Fake<|\bMockRepository\(")
E2E_PACKAGES = ("microsoft.playwright", "selenium.webdriver", "reqnroll")
INTEGRATION_PACKAGES = ("microsoft.aspnetcore.mvc.testing", "testcontainers", "aspire.hosting.testing", "respawn")
MUTABLE_INIT = re.compile(r"^(?:new\s+)?(?:Dictionary|List|ConcurrentDictionary|HashSet)\b|^\[\s*\]")
SKIP_ARG = re.compile(r"\bSkip\s*=")
THRESHOLD_RE = re.compile(r"<Threshold>\s*([\d,\s]+?)\s*</Threshold>")


def framework(packages: list) -> str:
    have = {p.lower() for p in packages}
    return next((name for name, ids in FRAMEWORKS if have & set(ids)), "unknown")


def test_kind(project: dict | None) -> str:
    if not project:
        return "unit"
    have, name = [p.lower() for p in project["packages"]], project["name"].lower()
    if any(p.startswith(E2E_PACKAGES) for p in have) or "acceptance" in name or "e2e" in name:
        return "e2e"
    if any(p.startswith(INTEGRATION_PACKAGES) for p in have) or "integration" in name or "functional" in name:
        return "integration"
    return "unit"


def _counts(d: dict) -> dict:
    counts = {"tests": 0, "classes": 0, "skips": 0, "xfails": 0, "fixtures": 0}
    for t in d["types"]:
        names = {a["name"] for a in t["attributes"]}
        has_test = False
        for m in t["members"]:
            if m["kind"] != "method":
                continue
            marks = [a for a in m["attributes"] if a["name"] in TEST_ATTRS]
            if marks:
                has_test = True
                counts["tests"] += 1
                if SKIP_ARG.search(" ".join(a["args"] for a in marks)) or any(a["name"] in SKIP_ATTRS for a in m["attributes"]):
                    counts["skips"] += 1
            if any(a["name"] in FIXTURE_ATTRS for a in m["attributes"]):
                counts["fixtures"] += 1
        if has_test or names & CLASS_ATTRS:
            counts["classes"] += 1
        if any(b.startswith(FIXTURE_BASES) or b.rsplit(".", 1)[-1].startswith(FIXTURE_BASES) for b in t["bases"]):
            counts["fixtures"] += 1
    return counts


def tests(decls: dict, projects: dict, texts, test_files) -> list:
    """One `test-file` item per file in `test_files`. `texts(path)` gives the file's text (for mock helpers) or None."""
    owner = {f: p for p in projects["projects"] if "language" not in p for f in p["files"]}
    items = []
    for path in sorted(test_files):
        if path not in decls:
            continue
        project = owner.get(path)
        items.append({"kind": "test-file", "path": path, "test_kind": test_kind(project), "framework": framework(project["packages"]) if project else "unknown",
                      **_counts(decls[path]), "mocks": len(MOCK_RE.findall(texts(path) or "")), "imports": [], "paths": []})
    return items


def _holds_collection(m: dict) -> bool:
    """A `static readonly` field set to a new collection: by its initialiser, or `new()` with a collection type."""
    init = (m.get("init") or "").strip()
    return bool(MUTABLE_INIT.match(init) or (re.match(r"new\s*\(", init) and re.match(r"(?:Dictionary|List|ConcurrentDictionary|HashSet)\b", m["type"] or "")))


def module_state(decls: dict, skip=frozenset()) -> list:
    """Static fields that hold changing data: not `readonly` or `const`, or `static readonly` set to a collection."""
    items = []
    for path in sorted(decls):
        if path in skip:
            continue
        for t in decls[path]["types"]:
            for m in t["members"]:
                if m["kind"] != "field" or not m["static"] or "const" in m["modifiers"]:
                    continue
                if "readonly" in m["modifiers"] and not _holds_collection(m):
                    continue
                snippet = " ".join([*m["modifiers"], m["type"] or "", m["name"]]).strip()
                items.append({"path": path, "line": m["line"], "end_line": m["end_line"], "category": "global-state", "rule": "dossier.csharp.state.static-mutable",
                              "name": m["name"], "snippet": snippet[:200], "detail": m["name"]})
    return sorted(items, key=lambda i: (i["path"], i["line"]))


def test_configs(tree, read, projects: dict) -> list:
    """`config` items: `*.runsettings`, `xunit.runner.json`, and a coverlet `<Threshold>` in a test project."""
    items = []
    test_projects = {p["path"] for p in projects["projects"] if "language" not in p and p["test"]}
    for path in sorted(tree):
        base = posixpath.basename(path)
        text = read(path) if base.endswith((".runsettings", ".csproj")) or base == "xunit.runner.json" else None
        if text is None:
            continue
        if base.endswith(".runsettings"):
            tool = "coverlet" if "coverlet" in base else "runsettings"
        elif base == "xunit.runner.json":
            tool = "xunit"
        elif path in test_projects and "<Threshold>" in text:
            tool = "coverlet"
        else:
            continue
        found = THRESHOLD_RE.search(text)
        numbers = [int(n) for n in re.findall(r"\d+", found.group(1))] if found else []
        items.append({"kind": "config", "path": path, "tool": tool, "settings": {"coverage_threshold": min(numbers)} if numbers else {}})
    return items
