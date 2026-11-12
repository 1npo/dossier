# Maintainer tools

Scripts the author runs by hand. None of them is part of `/dossier`, and Claude does not call them while it builds a dossier. Run each from the repository root.

| Script | Command | What it does |
|---|---|---|
| `bump_version.py` | `python3 tools/bump_version.py {major\|minor\|patch\|X.Y.Z}` | sets the version in `VERSION` and `.claude-plugin/plugin.json` |
| `refresh_eol.py` | `python3 tools/refresh_eol.py [--add PRODUCT]` | rewrites `src/dossier/data/eol.json` from endoflife.date |
| `golden.py` | `python3 tools/golden.py {repos\|capture\|compare}` | captures dossier output from two copies of the skill and compares them |
| `move_modules.py` | `python3 tools/move_modules.py MAP [--dry-run]` | moves modules and rewrites their imports |
| `ground_truth.py` | `python3 tools/ground_truth.py TRUTH REPORTS_DIR` | scores a dossier's reports against a ground-truth file |
| `skeleton.py` | `python3 tools/skeleton.py PAGE [PAGE...]` | prints the card skeleton of rendered pages and checks they match |
| `report_section.py` | `python3 tools/report_section.py HTML [RID] [--digest\|--cards]` | cuts one report's section out of a rendered page |

Each script's docstring lists its arguments in full.
