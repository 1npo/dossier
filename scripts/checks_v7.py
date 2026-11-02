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
}
FALLBACK = ("code that the rule for this pattern points at", "interactions")
CONFIRM = "Read the code at these places and check the reports that depend on them."
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
