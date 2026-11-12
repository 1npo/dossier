"""What `reading.map` and `conventions.tooling` know about JavaScript and TypeScript repositories (M4-20).

Pure functions of paths and file text. `measured.py` calls them next to its Python rules, so a Python-only tree gives the same rows as before.
"""
from __future__ import annotations

import json
import re

CONFIG_FILE = re.compile(r"(^|/)(package\.json|jsconfig\.json|tsconfig(\.[\w-]+)?\.json|\.env\.example|[\w.-]+\.config\.(js|cjs|mjs|ts))$")
BUILD_FILE = re.compile(r"(^|/)((vite|next|webpack|rollup|tsup)\.config\.(js|cjs|mjs|ts)|nx\.json|project\.json|turbo\.json)$")

# tool -> (pattern for its config files, keys of package.json that configure it). Matched on the whole path, so apps/* are found too.
NODE_TOOLS = {
    "eslint": (re.compile(r"(^|/)(\.eslintrc(\.(js|cjs|mjs|json|ya?ml))?|eslint\.config\.(js|cjs|mjs|ts|mts|cts))$"), ("eslintConfig",)),
    "prettier": (re.compile(r"(^|/)(\.prettierrc(\.(json|ya?ml|toml|js|cjs|mjs))?|prettier\.config\.(js|cjs|mjs|ts))$"), ("prettier",)),
    "biome": (re.compile(r"(^|/)biome\.jsonc?$"), ()),
    "typescript": (re.compile(r"(^|/)tsconfig(\.[\w-]+)?\.json$"), ()),
    "husky": (re.compile(r"(^|/)\.husky/[^/]+$"), ()),
    "lint-staged": (re.compile(r"(^|/)(\.lintstagedrc(\.\w+)?|lint-staged\.config\.(js|cjs|mjs|ts))$"), ("lint-staged",)),
    "commitlint": (re.compile(r"(^|/)(\.commitlintrc(\.\w+)?|commitlint\.config\.(js|cjs|mjs|ts))$"), ("commitlint",)),
}
# Words that stand for a tool in a CI file or a hook, where its own name is not what gets written.
CI_NAMES = {"typescript": r"typescript|tsc|typecheck|type-check"}
HOOK_FILE = re.compile(r"(^|/)\.husky/[^/]+$")


def is_config(path: str) -> bool:
    return bool(CONFIG_FILE.search(path))


def is_build(path: str, read) -> bool:
    """A build tool's config file, or a `package.json` with a `build` script (needs `read`)."""
    if BUILD_FILE.search(path):
        return True
    if path.rsplit("/", 1)[-1] != "package.json" or read is None:
        return False
    return "build" in (manifest(read(path)).get("scripts") or {})


def manifest(text) -> dict:
    try:
        data = json.loads(text or "")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def tool_locations(tree, read, line_of) -> dict:
    """tool -> [(path, line or None)] for every JavaScript tool with a config file or a `package.json` key.

    `line_of(text, marker)` is `measured._line_of`. A `package.json` key counts, with `package.json` as the file."""
    found: dict = {}
    for tool, (pattern, keys) in NODE_TOOLS.items():
        where = [(p, None) for p in sorted(tree) if pattern.search(p)]
        for p in sorted(tree):
            if keys and p.rsplit("/", 1)[-1] == "package.json" and read is not None:
                text = read(p) or ""
                data = manifest(text)
                for key in keys:
                    if key in data:
                        where.append((p, line_of(text, f'"{key}"')))
                        break
        if where:
            found[tool] = where
    return found


def ci_pattern(tool: str):
    names = CI_NAMES.get(tool) or re.escape(tool)
    return re.compile(r"(?<![\w-])(" + names + r")(?![\w-])", re.I)
