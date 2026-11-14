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
import argparse

__all__ = ["cmd_candidates"]


EMPTY_GUARD_FILES = 20  # a repository with more source files than this is not expected to have no findings for a report
TOOL_REPORTS = ("entry", "io", "data", "behavior", "ops")


def _empty_guard(rid, extract, tree):
    """A sentence when a tool-fed report has no findings although the repository has code, else None."""
    if rid not in TOOL_REPORTS or not tree or candidates.for_report(rid, extract):
        return None
    n = len(components.source_files(tree, extract))
    if n <= EMPTY_GUARD_FILES:
        return None
    return (f"There are no tool findings for the '{rid}' report, but the repository has {n} source files. The tools may not "
            "have run or their output may have been discarded (look at tool_report and the extract filter in the prepare output, "
            "and at build.json). Do not take this empty list as proof that the code has none of these.")


def cmd_candidates(a: argparse.Namespace) -> None:
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
    warning = _empty_guard(a.report, extract, tree)
    if warning:
        print(f"warning: {warning}", file=sys.stderr)
    if a.json:
        print(json.dumps(candidates.report_data(a.report, extract, reports, facts, only_open=a.open, catalog=catalog, tree=tree), indent=1))
    else:
        if warning:
            sys.stdout.write(f"!! {warning}\n\n")
        sys.stdout.write(candidates.text(a.report, extract, reports, facts, only_open=a.open, catalog=catalog, tree=tree))
