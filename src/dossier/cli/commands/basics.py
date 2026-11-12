from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys

from dossier.core import buildlog
from dossier.core import config
from dossier.pipeline import workarea
from dossier.render import portfolio
from dossier.tooling import toolcheck
from dossier.cli import common


def cmd_version(_):
    print(f"dossier {common.VERSION}")


def cmd_portfolio(_):
    print(f"Portfolio written to {portfolio.write(common.get_home(), common.VERSION)}")


def cmd_home(a):
    if not a.dir:
        h = config.home()
        print(f"Dossier home: {h}" if h else "No dossier home is set. Run /dossier home <directory>.")
        return
    d = Path(a.dir).expanduser().resolve()
    d.mkdir(parents=True, exist_ok=True)
    config.update(home=str(d))
    print(f"Dossier home set to {d}")


def skill_line(skill: dict) -> str:
    if skill["commit"] is None:
        return f"skill: {skill['path']} (not a git work tree)"
    if skill["unmerged"]:
        return f"skill: {skill['commit'][:7]} (UNMERGED: run git status in {skill['path']})"
    return f"skill: {skill['commit'][:7]} ({'dirty' if skill['dirty'] else 'clean'})"


def cmd_doctor(a):
    if a.all:
        report = toolcheck.preflight([], all_scopes=True)
    else:
        top = common.toplevel(a.repo)
        sha = subprocess.run(["git", "-C", top, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        report = toolcheck.preflight_at(top, sha)
    skill = buildlog.skill_state(common.ROOT)
    if a.json:
        print(json.dumps(dict(report, skill=skill), indent=1))
    else:
        print(toolcheck.format_text(report))
        print(skill_line(skill))
    sys.exit(1 if report["missing"] or skill["unmerged"] else 0)


def cmd_clean(a):
    top = common.toplevel(a.repo)
    out, name, _ = common.out_dir(top)
    root = config.cache_root()
    area = root / out.name
    try:
        removed = workarea.clean(area, root)
    except workarea.CheckoutError as e:
        common.die(str(e))
    print(f"Removed the working area {area}. The dossier in {out} was not touched." if removed else f"Nothing to clean for {name}.")
