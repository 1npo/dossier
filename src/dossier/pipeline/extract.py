"""The extract stage: run each detected adapter on the clean copy, filter its paths, and save extract/*.json.

An adapter's saved section is reused while its key (commit, adapter version, tool versions, rule digest, code digest)
is unchanged. The adapter interface is `dossier.adapters.base`; the shipped adapters are `dossier.adapters.registry`.
"""
from __future__ import annotations

import fnmatch
import functools
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath

from dossier import resources
from dossier.adapters.base import ALWAYS_EXPECTED_SEG, NO_EXTRACTORS, OUTPUTS, Adapter, Context
from dossier.facts import gather
from dossier.facts import resources as resource_files
from dossier.findings import candidates
from dossier.pipeline import workarea
from dossier.tooling import sandbox
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dossier.tooling.shared_tools import Semgrep, TreeSitter

__all__ = ["run_extract", "write_resources"]


# ------------------------------------------------------------------ path filter


def _is_expected(path: str, globs) -> bool:
    segs = set(path.split("/")[:-1]) | {path.split("/")[0]}
    if segs & (gather.VENDOR_SEG | gather.GENERATED_SEG | ALWAYS_EXPECTED_SEG):
        return True
    return any(fnmatch.fnmatch(path, g) for g in globs)


def filter_paths(outputs: dict, tree, checkout, expected_globs=()) -> tuple:
    """Keep only items whose paths are tracked at the commit. Returns (kept outputs, stats)."""
    root = Path(checkout).resolve()
    stats: dict = {"paths_seen": 0, "paths_dropped": 0, "dropped_expected": 0, "dropped_outside": 0,
             "dropped_unexpected": 0, "unexpected": []}

    def check(p):
        """Return the repository-relative path, or None when dropped (and count why)."""
        stats["paths_seen"] += 1
        if os.path.isabs(p) or PureWindowsPath(p).is_absolute():
            try:
                p = PurePosixPath(Path(p).resolve().relative_to(root)).as_posix()
            except ValueError:
                stats["paths_dropped"] += 1
                stats["dropped_outside"] += 1
                return None
        else:
            p = p.replace("\\", "/")  # tool adapters on Windows report backslash paths; the tree uses "/"
        p = p[2:] if p.startswith("./") else p
        if p in tree:
            return p
        stats["paths_dropped"] += 1
        if _is_expected(p, expected_globs):
            stats["dropped_expected"] += 1
        else:
            stats["dropped_unexpected"] += 1
            stats["unexpected"].append(p)
        return None

    kept = {}
    for name, items in outputs.items():
        out = []
        for it in items:
            if not isinstance(it.get("path"), str):
                raise ValueError(f"an item in '{name}' has no path")
            p = check(it["path"])
            if p is None:
                continue
            it = {**it, "path": p}
            if "paths" in it:
                it["paths"] = [q for q in (check(x) for x in it["paths"]) if q is not None]
            out.append(it)
        kept[name] = out
    stats["unexpected"] = sorted(set(stats["unexpected"]))
    for name, items in kept.items():  # invariant: a kept path is a tracked path with "/" separators
        for it in items:
            for q in [it["path"], *it.get("paths", [])]:
                if q not in tree or "\\" in q:
                    raise AssertionError(f"kept path {q!r} in '{name}' is not a tracked, normalized path")
    return kept, stats


# ------------------------------------------------------------------ resources: non-code files the code reads


def write_resources(out: Path, sha: str, tree, checkout) -> dict:
    """Find the non-code files that code reads (`facts.resources`), give each group a finding id, and save `extract/resources.json`.

    Not an adapter: it looks at every language at once, and runs on every prepare because it is cheap. Returns counts for build.json."""
    root = Path(checkout)

    def read(path):
        try:
            return (root / path).read_text(encoding="utf-8")
        except (OSError, ValueError):
            return None

    items = candidates.assign_ids("resources", resource_files.detect(tree, read))
    _write(out, "resources", {"schema": 1, "sha": sha, "adapters": {"resources": {"sha": sha, "items": items}}})
    return {"groups": len(items), "files": sum(i["count"] for i in items), "unreferenced": sum(1 for i in items if not i["referenced_by"])}


# ------------------------------------------------------------------ extract stage


def _read(out: Path, name: str) -> dict:
    f = out / "extract" / f"{name}.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {"schema": 1, "sha": None, "adapters": {}}


def _write(out: Path, name: str, data: dict) -> None:
    d = out / "extract"
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f"{name}.json.tmp"
    tmp.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, d / f"{name}.json")


def rules_hash(folders) -> str:
    """A digest of every rule file (name and bytes) in `folders`, so a rule change can invalidate a build."""
    h = hashlib.sha256()
    for folder in folders:
        for f in sorted(Path(folder).glob("*.yml")):
            h.update(f"{f.parent.name}/{f.name}\0".encode() + f.read_bytes() + b"\0")
    return h.hexdigest()[:16]


PACKAGE = resources.skill_root() / "src" / "dossier"


def code_hash(folder=None) -> str:
    """A digest of the skill's own code (every module under `src/dossier/`, the workers included, every launcher in
    `scripts/`, `data/tools.json` and `VERSION`), so a change to an adapter or to anything it calls invalidates a saved
    extract. Without it a fix to extraction code kept showing the old rows for the same commit. `folder` is the package
    folder; the skill root is two levels above it."""
    folder = Path(folder) if folder else PACKAGE
    root = folder.parents[1]
    h = hashlib.sha256()
    files = sorted(list(folder.rglob("*.py")) + list((root / "scripts").glob("*.py")), key=lambda f: f.relative_to(root).as_posix())
    files += [f for f in (folder / "data" / "tools.json", root / "VERSION") if f.exists()]
    for f in files:
        h.update(f.relative_to(root).as_posix().encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()[:16]


def _key(adapter, sha, tool_versions):
    return {"sha": sha, "version": adapter.version, "tools": {t: tool_versions.get(t) for t in adapter.tools},
            "rules": rules_hash(adapter.rules), "code": code_hash()}


def _reusable(out: Path, adapter, key) -> bool:
    found = False
    for o in OUTPUTS:
        sec = _read(out, o)["adapters"].get(adapter.name)
        if sec is None:
            continue
        found = True
        if {"sha": sec.get("sha"), "version": sec.get("version"), "tools": sec.get("tools"), "rules": sec.get("rules"),
                "code": sec.get("code")} != key:
            return False
        if any(t.get("status") != "ok" for t in (sec.get("tool_status") or {}).values()):
            return False
    return found


def run_extract(*, adapters: Sequence[Adapter], checkout: str | Path, sha: str, tree: frozenset[str], area: Path, out: Path, trusted: dict, allow_ref: bool, restored: dict, treesitter: TreeSitter, semgrep: Semgrep,
                tool_versions: dict[str, str], timeout: float) -> dict:
    checkout, out = Path(checkout), Path(out)

    def fail(reason):
        return {"status": "failed", "reason": reason, "counts": {}, "details": {"adapters": []}}

    ok, why = workarea.verify(checkout, sha)
    if not ok:
        return fail(f"The clean copy was not ready for extraction. {why}")
    if not adapters:
        return {"status": "skipped", "reason": NO_EXTRACTORS, "counts": {}, "details": {"adapters": []}}

    results, produced = [], {}
    totals = {"paths_seen": 0, "paths_dropped": 0, "dropped_expected": 0, "dropped_outside": 0, "dropped_unexpected": 0}
    unexpected: list = []
    for ad in adapters:
        key = _key(ad, sha, tool_versions)
        res: dict = {"name": ad.name, "version": ad.version, "status": "ok", "reason": None}
        results.append(res)
        if ad.loads_repo_code and not trusted["trusted"] and not allow_ref:
            res.update(status="skipped", reason=f"{trusted['why'][0].upper()}{trusted['why'][1:]}. Use --allow-ref to run it.")
            continue
        if _reusable(out, ad, key):
            res["status"] = "reused"
            continue
        files = sorted(p for p in tree if not gather.noise_reason(p) and (gather.lang_of(p) or ("",))[0] in ad.languages)
        run = functools.partial(sandbox.run, area=area, cwd=checkout, timeout=timeout,
                                profile="restricted" if ad.loads_repo_code else "tool")
        ctx = Context(checkout=checkout, sha=sha, tree=tree, files=files, area=Path(area), restored=restored, run=run,
                      treesitter=treesitter, semgrep=semgrep, tool_versions=tool_versions,
                      trusted=bool(trusted["trusted"] or allow_ref), repo_name=out.name)
        try:
            raw = ad.extract(ctx)
            unknown = set(raw) - set(OUTPUTS)
            if unknown:
                raise ValueError(f"unknown output {sorted(unknown)[0]}")
            kept, stats = filter_paths(raw, tree, checkout, ad.expected_untracked)
            kept = {o: (candidates.assign_ids(o, its) if o in candidates.ID_OUTPUTS else its) for o, its in kept.items()}
        except Exception as e:  # one adapter failing must not stop the others
            res.update(status="failed", reason=((str(e).splitlines() or [""])[0] or type(e).__name__))
            continue
        res["tools"] = ctx.tool_status
        if ctx.details:
            res["details"] = ctx.details
        produced[ad.name] = (key, kept, ctx.tool_status)
        for k in totals:
            totals[k] += stats[k]
        unexpected += stats["unexpected"]

    ok, why = workarea.verify(checkout, sha)
    if not ok:
        return fail("The clean copy changed during extraction (HEAD or tracked files).")

    for o in OUTPUTS:
        data = _read(out, o)
        changed = False
        for name, (key, kept, tool_status) in produced.items():
            if o in kept:
                data["adapters"][name] = {**key, "tool_status": tool_status, "items": kept[o]}
                changed = True
            elif name in data["adapters"]:
                del data["adapters"][name]
                changed = True
        if changed:
            data["sha"] = sha
            _write(out, o, data)

    statuses = {r["status"] for r in results}
    if statuses == {"reused"}:
        status, reason = "reused", None
    elif statuses <= {"skipped"}:
        status, reason = "skipped", "; ".join(f"{r['name']}: {r['reason']}" for r in results)
    elif statuses <= {"failed"}:
        status, reason = "failed", "; ".join(f"{r['name']}: {r['reason']}" for r in results)
    else:
        status, reason = "ok", None
    counts = {"adapters": len(results), "ran": sum(r["status"] == "ok" for r in results),
              "reused": sum(r["status"] == "reused" for r in results), **totals}
    return {"status": status, "reason": reason, "counts": counts,
            "details": {"adapters": results, "unexpected": sorted(set(unexpected))},
            "tools": [{"name": k, "version": v} for k, v in sorted(tool_versions.items())]}
