"""`check`: audit a written page, and the browser check it may run. Reads the HTML and the build log;
never rewrites the page.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from dossier.checks import page_audit
from dossier.core import buildlog
from dossier.findings import candidates
from dossier.render import page as render
from dossier.render import summary
from dossier.cli import common

__all__ = ["browser_check_line", "cmd_check"]


def browser_check_line(build) -> str:
    """What the render summary says about the browser check: "not run", or how many problems it found and when."""
    rec = buildlog.latest(build, "check", "browser") if build else None
    if not rec:
        return "not run"
    n = (rec.get("counts") or {}).get("problems", 0)
    return f"{n} problem{'' if n == 1 else 's'} at {render.local_stamp(rec.get('started') or '')}"


def run_browser_check(html: Path, out: Path):
    """(exit code, output) of check_page.py on `html`; it records its result in build.json."""
    cmd = ["uv", "run", str(common.ROOT / "scripts" / "check_page.py"), str(html), "--shots", str(out / ".check-shots")]
    if (out / buildlog.FILE).exists():
        cmd += ["--record", str(out / buildlog.FILE)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def cmd_check(a):
    """The two checks of the written page: V11 (it draws every row and entry of its sources), then V12 (the browser)."""
    top = common.toplevel(a.repo)
    out, name, _ = common.out_dir(top)
    html = out / f"dossier-{name}.html"
    if not html.exists():
        common.die(f"There is no page at {html}. Run render first.")
    reports = {rid: common.load(out / "reports" / f"{rid}.json") for rid, _, authored in render.REPORTS
               if authored and (out / "reports" / f"{rid}.json").exists()}
    facts = common.load(out / "facts.json")
    extract = candidates.load(out)
    try:
        facts["dependencies"] = common.load(out / "dependencies.json")
        measured = render.measured_ctx({"cites": render.Cites(facts), "extract": extract}, reports, facts)
    except Exception:  # noqa: BLE001 - a repository that cannot be opened here: the new cards are then not counted
        measured = None
    audit = page_audit.audit(html.read_text(encoding="utf-8"), reports, extract, facts, build=buildlog.load(out), measured=measured)
    for line in audit:
        print(f"FAIL {line}")
    v8 = summary.check_file(out, facts, common.VERSION)
    for line in v8:
        print(f"FAIL {line}")
    code, text = run_browser_check(html, out)
    print(text.rstrip())
    browser = sum(1 for line in text.splitlines() if line.startswith("FAIL"))
    problems = len(audit) + len(v8) + (browser or (1 if code else 0))
    print(f"problems: {problems}")
    sys.exit(1 if problems else 0)
