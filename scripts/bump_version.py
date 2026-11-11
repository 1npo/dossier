#!/usr/bin/env python3
"""Bump the skill's version in the two places that hold it: `VERSION` and `.claude-plugin/plugin.json`.

Usage: python3 scripts/bump_version.py {major|minor|patch|X.Y.Z}

Prints the new version. Commit the result on a `chore/release-X.Y.Z` branch and merge it to `main`:
the release workflow tags and publishes when a push to `main` changes `VERSION`.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def bump(current: str, how: str) -> str:
    m = SEMVER.match(current)
    if not m:
        raise ValueError(f"current version {current!r} is not X.Y.Z")
    major, minor, patch = map(int, m.groups())
    if how == "major":
        return f"{major + 1}.0.0"
    if how == "minor":
        return f"{major}.{minor + 1}.0"
    if how == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if SEMVER.match(how):
        return how
    raise ValueError(f"expected major, minor, patch or X.Y.Z, got {how!r}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    version_file = ROOT / "VERSION"
    manifest = ROOT / ".claude-plugin" / "plugin.json"
    try:
        new = bump(version_file.read_text().strip(), argv[1])
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    data = json.loads(manifest.read_text())
    data["version"] = new
    manifest.write_text(json.dumps(data, indent=2) + "\n")
    version_file.write_text(new + "\n")
    print(new)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
