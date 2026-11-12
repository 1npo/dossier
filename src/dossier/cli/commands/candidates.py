"""`candidates`: list the tool findings a report must keep, merge or dismiss. Read only.
"""
from __future__ import annotations

import json
import sys

from dossier.findings import candidates
from dossier.findings import components
from dossier.pipeline import stages
from dossier.render import page as render
from dossier.cli import common


def cmd_candidates(a):
    top = common.toplevel(a.repo)
    out, _, _ = common.out_dir(top)
    ids = [rid for rid, _, authored in render.REPORTS if authored]
    if a.report not in ids:
        common.die(f"'{a.report}' is not a report Claude writes. Use one of: {', '.join(ids)}.")
    extract = candidates.load(out)
    if not extract:
        common.die("No extractor output found. Run prepare first.")
    facts = common.load(out / "facts.json", {})
    facts["file_lines"] = components.chunk_lines(common.load(out / "chunks.json", {}))
    reports = {rid: common.load(out / "reports" / f"{rid}.json") for rid in ids if (out / "reports" / f"{rid}.json").exists()}
    catalog = common.load(a.catalog) if a.catalog else None
    sha = facts.get("repo", {}).get("sha")
    tree = stages.tree_at(top, sha) if sha else None
    if a.json:
        print(json.dumps(candidates.report_data(a.report, extract, reports, facts, only_open=a.open, catalog=catalog, tree=tree), indent=1))
    else:
        sys.stdout.write(candidates.text(a.report, extract, reports, facts, only_open=a.open, catalog=catalog, tree=tree))
