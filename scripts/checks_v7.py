"""V7: blind-spot hits are recorded in Gaps (D6). Never fails the build.

Split out of `checks.py` to keep that module short. The wording is fixed so Gaps item ids stay the same across builds.
"""
from __future__ import annotations

# pattern id -> (what static analysis may miss there, the report that owns the closest card)
BLIND_SPOTS = {
    "dynamic-import": ("imports made at run time", "interactions"),
    "entry-point-loading": ("plugins loaded from installed packages", "interactions"),
    "string-plugin": ("plugins named by a string", "interactions"),
    "decorator-registry": ("handlers registered by decorator and called through a table", "interactions"),
    "getattr-dispatch": ("methods chosen by name at run time", "interactions"),
    "django-apps": ("Django apps loaded from settings", "interactions"),
    "django-signals": ("signal handlers called by Django", "interactions"),
    "pytest-fixtures": ("fixtures passed to tests by name", "behavior"),
    "codegen": ("generated code, whose generator was not analysed", "components"),
    "feature-flag": ("behaviour switched by flags at run time", "components"),
    "computed-subcommand": ("command-line commands registered under a computed name", "entry"),
    "dynamic-require": ("modules loaded through `require` with a computed name", "interactions"),
    "barrel-reexport": ("names passed on through a barrel file, so an import may point at the barrel and not the real source", "interactions"),
    "react-context": ("values passed through React context", "interactions"),
    "hook-wiring": ("behaviour wired up inside custom hooks", "interactions"),
    "string-route": ("routes whose path is built at run time", "entry"),
    "route-mount": ("routes mounted under a prefix, so their full path is not the one written beside them", "entry"),
    "module-federation": ("code loaded from other builds through module federation", "interactions"),
    "di-registration": ("objects built and passed in by a dependency injection container", "interactions"),
}
FALLBACK = ("code that the rule for this pattern points at", "interactions")
CONFIRM = "Read the code at these places and check the reports that depend on them."
KNOWN_LIMIT = "This is a known limit of this version of dossier."
STALE_FLAGS = "Stale feature flags and unused routes are not detected for {language}."
RUNTIME_CONFIG = "Code chosen at run time by configuration (for example a class name in a settings file) is not detected by any rule."


def v7(extract: dict) -> tuple[list, list, list, dict]:
    """(errors, warnings, gaps, counts): one coverage item per blind-spot group (pattern, file), then the fixed runtime-configuration item."""
    groups: dict = {}
    for it in (extract or {}).get("blindspots", []):
        groups.setdefault((it.get("pattern", ""), it["path"]), []).append(it)
    gaps = []
    for (pattern, path), hits in sorted(groups.items()):
        missed, report = BLIND_SPOTS.get(pattern, FALLBACK)
        first = min(hits, key=lambda h: h.get("line") or 0)
        where = f"{path}:{first['line']}" if first.get("line") else path
        gaps.append({"kind": "coverage", "report": report,
                     "statement": f"Static analysis may miss {missed} here: {len(hits)} place(s) in [[{where}]].",
                     "how_to_confirm": CONFIRM})
    if any(g.get("kind") == "module" for g in (extract or {}).get("graph", [])):
        gaps.append({"kind": "coverage", "report": "interactions", "statement": RUNTIME_CONFIG, "how_to_confirm": CONFIRM})
    return [], [], gaps, {"v7": len(groups)}


def js_coverage(extract: dict) -> list:
    """Fixed Gaps items for JavaScript and TypeScript (D10, D17), and the stale-flags item for each language that has a module.

    The Python item appears only for a module with no `language` key, the JavaScript one only for `language: "js"`.
    """
    graph = (extract or {}).get("graph", [])
    items = []
    modules = [g for g in graph if g.get("kind") == "module"]
    if any("language" not in m for m in modules):
        items.append({"kind": "coverage", "report": "change", "statement": STALE_FLAGS.format(language="Python"), "how_to_confirm": KNOWN_LIMIT})
    if any(m.get("language") == "js" for m in modules):
        items.append({"kind": "coverage", "report": "change", "statement": STALE_FLAGS.format(language="JavaScript or TypeScript"),
                      "how_to_confirm": KNOWN_LIMIT})
    for note in sorted((g for g in graph if g.get("kind") == "js-note"), key=lambda g: (g["note"], g["name"])):
        name = note["name"]
        if note["note"] == "framework":
            items.append({"kind": "coverage", "report": "entry", "how_to_confirm": KNOWN_LIMIT,
                          "statement": f"Routes written for {name} are not detected, so check the entry points by hand."})
        elif note["note"] == "bun":
            items.append({"kind": "coverage", "report": "dossier", "how_to_confirm": KNOWN_LIMIT,
                          "statement": f"The packages of {name} were not installed, because dossier does not install from Bun lockfiles."})
        elif note["note"] == "unscanned":
            items.append({"kind": "coverage", "report": "dossier", "how_to_confirm": "Read these files by hand.",
                          "statement": f"{name} .mts or .cts file(s) were not scanned by the pattern rules."})
        elif note["note"] == "api":
            package, _, subpath = name.partition("|")
            items.append({"kind": "coverage", "report": "io", "how_to_confirm": "Read this package's entry file by hand.",
                          "statement": f"The public API of {package} could not be fully worked out from {subpath}."})
    return items
