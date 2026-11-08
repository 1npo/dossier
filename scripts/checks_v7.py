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
    "di-scan": ("services registered by scanning assemblies, so which classes are used is decided at run time", "interactions"),
    "di-resolution": ("objects fetched from the dependency injection container by type while the program runs", "interactions"),
    "reflection": ("code found or called through reflection", "interactions"),
    "route-convention": ("routes changed by MVC conventions, so their full path may differ from the attributes beside them", "entry"),
    "conventional-route": ("controller actions reached through a route template, which have no path of their own in the code", "entry"),
    "mvc-filter": ("filters that run before or after requests, attached by attribute or registration", "interactions"),
    "mediator-handler": ("requests passed to their handlers by a mediator library, so the call does not name the code that runs", "interactions"),
    "source-generator": ("code generated at build time, which is not in the repository and was not read", "components"),
    "partial-class": ("a type split across several files with `partial`, so one file shows only part of it", "components"),
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


CS_LINKS = "C# file links come from type names in the text; uses through extension methods, var, reflection or dependency injection are not linked."
CS_DEAD = ("C# dead code is listed only for internal types that nothing references; a class found by reflection or registered by scanning "
           "can be listed wrongly, so check before removing anything.")
CS_NOTES = {  # note -> (report, how to confirm, statement with {name} / {a} / {b})
    "framework": ("entry", KNOWN_LIMIT, "Routes and handlers written for {name} are not detected, so check the entry points by hand."),
    "no-lock": ("dossier", KNOWN_LIMIT, "The packages of {name} were not installed, because it has no packages.lock.json and dossier installs only from lock files."),
    "sdk": ("dossier", "Install the SDK named here and build again.", "The C# tools that need the .NET SDK did not run: {name}"),
    "razor": ("dossier", "Read these files by hand.", "{name} Razor or Blazor file(s) were not read by the reference index or the pattern rules; only their @page routes were found."),
    "generator": ("components", KNOWN_LIMIT, "Code generated at build time by {a} in {b} is not in the repository, and static analysis did not read it."),
    "ambiguous-name": ("interactions", KNOWN_LIMIT, "{name} type name(s) are declared more than once in visible namespaces, so uses of them were not linked between files."),
    "ambiguous-symbol": ("interactions", KNOWN_LIMIT, "{name} name(s) were given the same identity by scip-dotnet, so references to them were not counted."),
    "unindexed": ("interactions", "Read these files by hand.", "{name} C# file(s) are not in the scip-dotnet index, so references from and to them were not counted."),
    "msbuild": ("dossier", "Build the solution once with dotnet build and read the errors.", "scip-dotnet could not load every project: {name}"),
    "api": ("io", "Read this project's public types by hand.", "The public API of {name} could not be fully worked out."),
    "dead": ("change", KNOWN_LIMIT, CS_DEAD),
}


def cs_coverage(extract: dict) -> list:
    """Fixed Gaps items for C# (D10): the stale-flags and file-link sentences when a C# module exists, then one item per `cs-note`.

    The Python and JavaScript items are not touched: a C# module has `language: "csharp"`."""
    graph = (extract or {}).get("graph", [])
    items = []
    if any(g.get("kind") == "module" and g.get("language") == "csharp" for g in graph):
        items.append({"kind": "coverage", "report": "change", "statement": STALE_FLAGS.format(language="C#"), "how_to_confirm": KNOWN_LIMIT})
        items.append({"kind": "coverage", "report": "interactions", "statement": CS_LINKS, "how_to_confirm": KNOWN_LIMIT})
    for note in sorted((g for g in graph if g.get("kind") == "cs-note"), key=lambda g: (g["note"], g["name"])):
        if note["note"] not in CS_NOTES:
            continue
        report, confirm, text = CS_NOTES[note["note"]]
        a, _, b = note["name"].partition("|")
        items.append({"kind": "coverage", "report": report, "how_to_confirm": confirm, "statement": text.format(name=note["name"], a=a, b=b)})
    return items
