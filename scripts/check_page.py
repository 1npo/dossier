#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright"]
# ///
"""Run the browser page check from the skill folder: `uv run scripts/check_page.py DOSSIER.html [--shots DIR]`.

uv reads the header above and runs this file in a cached environment with Playwright; nothing is
installed into the skill folder. The code is `dossier.checks.browser` in ../src; this file only puts
that folder first on sys.path (replacing this file's own folder, so `import dossier` cannot find this file).
"""
import sys
from pathlib import Path

sys.path[0] = str(Path(__file__).resolve().parent.parent / "src")

from dossier.checks.browser import main  # noqa: E402

if __name__ == "__main__":
    main()
