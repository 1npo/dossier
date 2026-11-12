"""`verify-sample` and `verify-record`: pick cited claims for the independent check and record its
verdicts in the build log.
"""
from __future__ import annotations

import json
import secrets

from dossier.checks import verify
from dossier.core import buildlog
from dossier.core import config
from dossier.render import page as render
from dossier.cli import common


def _verify_inputs(a):
    top = common.toplevel(a.repo)
    out, _, _ = common.out_dir(top)
    facts = common.load(out / "facts.json")
    build = buildlog.load(out)
    if not facts or not build:
        common.die("There is no build to check. Run prepare and render first.")
    return out, facts, build


def cmd_verify_sample(a):
    out, facts, build = _verify_inputs(a)
    reports = {rid: common.load(out / "reports" / f"{rid}.json") for rid, _, authored in render.REPORTS
               if authored and (out / "reports" / f"{rid}.json").exists()}
    cites = render.Cites(facts)
    per = a.per_report or config.verify_per_report()
    seed = a.seed or secrets.token_hex(8)
    items = verify.sample(verify.eligible(reports, cites), seed, per, cites)
    buildlog.append(out / buildlog.FILE, verify.sample_record(seed, per, items))
    print(json.dumps({"seed": seed, "sha": facts["repo"]["sha"], "prompt": str(common.ROOT / "prompts" / "verify.md"), "items": items}, indent=1))


def cmd_verify_record(a):
    out, _, build = _verify_inputs(a)
    sample = buildlog.latest(build, "check", "verify-sample")
    if not sample:
        common.die("No claims have been sampled. Run verify-sample first.")
    results = common.load(a.results)
    problems = verify.check_results(sample, results)
    if problems:
        common.die("\n".join(problems))
    buildlog.append(out / buildlog.FILE, verify.result_record(sample, results))
    print(f"Recorded {len(results)} verdicts.")
