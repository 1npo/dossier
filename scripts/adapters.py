"""The adapter interface, the extract stage and the path filter.

An adapter turns one language's code into the standard outputs (entry points, import graph, symbols, ...).
M1 ships the interface only; the Python adapter arrives in M2.
"""
from __future__ import annotations

import fnmatch
import functools
import json
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable

import gather
import sandbox
import shared_tools
import workarea

OUTPUTS = ("entry_points", "graph", "symbols", "io_candidates", "models", "tests", "dead", "blindspots")
ALWAYS_EXPECTED_SEG = {".venv", "venv", ".git", ".grimp_cache"}
NO_EXTRACTORS = "No extractors exist for these languages in this version of dossier."


@dataclass
class Context:
    checkout: Path
    sha: str
    tree: frozenset
    files: list
    area: Path
    restored: dict
    run: Callable
    treesitter: shared_tools.TreeSitter
    semgrep: shared_tools.Semgrep
    tool_versions: dict


class Adapter:
    name = ""
    version = "1"
    languages: tuple = ()
    tools: tuple = ()
    loads_repo_code = False
    expected_untracked: tuple = ()
    blind_spots: tuple = ()

    def extract(self, ctx: Context) -> dict:
        """Return {output name: [items]} for any subset of OUTPUTS. Every item has 'path'."""
        raise NotImplementedError


ADAPTERS: tuple = ()


def detect(languages: list, adapters=ADAPTERS) -> list:
    return [a() if isinstance(a, type) else a for a in adapters if set(a.languages) & set(languages)]


# ------------------------------------------------------------------ path filter


def _is_expected(path: str, globs) -> bool:
    segs = set(path.split("/")[:-1]) | {path.split("/")[0]}
    if segs & (gather.VENDOR_SEG | gather.GENERATED_SEG | ALWAYS_EXPECTED_SEG):
        return True
    return any(fnmatch.fnmatch(path, g) for g in globs)


def filter_paths(outputs: dict, tree, checkout, expected_globs=()) -> tuple:
    """Keep only items whose paths are tracked at the commit. Returns (kept outputs, stats)."""
    root = Path(checkout).resolve()
    stats = {"paths_seen": 0, "paths_dropped": 0, "dropped_expected": 0, "dropped_outside": 0,
             "dropped_unexpected": 0, "unexpected": []}

    def check(p):
        """Return the repository-relative path, or None when dropped (and count why)."""
        stats["paths_seen"] += 1
        if os.path.isabs(p):
            try:
                p = PurePosixPath(Path(p).resolve().relative_to(root)).as_posix()
            except ValueError:
                stats["paths_dropped"] += 1
                stats["dropped_outside"] += 1
                return None
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
    return kept, stats


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


def _key(adapter, sha, tool_versions):
    return {"sha": sha, "version": adapter.version, "tools": {t: tool_versions.get(t) for t in adapter.tools}}


def _reusable(out: Path, adapter, key) -> bool:
    found = False
    for o in OUTPUTS:
        sec = _read(out, o)["adapters"].get(adapter.name)
        if sec is None:
            continue
        found = True
        if {"sha": sec.get("sha"), "version": sec.get("version"), "tools": sec.get("tools")} != key:
            return False
    return found


def run_extract(*, adapters, checkout, sha, tree, area, out, trusted, allow_ref, restored, treesitter, semgrep,
                tool_versions, timeout) -> dict:
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
        res = {"name": ad.name, "version": ad.version, "status": "ok", "reason": None}
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
        ctx = Context(checkout, sha, tree, files, Path(area), restored, run, treesitter, semgrep, tool_versions)
        try:
            raw = ad.extract(ctx)
            unknown = set(raw) - set(OUTPUTS)
            if unknown:
                raise ValueError(f"unknown output {sorted(unknown)[0]}")
            kept, stats = filter_paths(raw, tree, checkout, ad.expected_untracked)
        except Exception as e:  # one adapter failing must not stop the others
            res.update(status="failed", reason=((str(e).splitlines() or [""])[0] or type(e).__name__))
            continue
        produced[ad.name] = (key, kept)
        for k in totals:
            totals[k] += stats[k]
        unexpected += stats["unexpected"]

    ok, why = workarea.verify(checkout, sha)
    if not ok:
        return fail("The clean copy changed during extraction (HEAD or tracked files).")

    for o in OUTPUTS:
        data = _read(out, o)
        changed = False
        for name, (key, kept) in produced.items():
            if o in kept:
                data["adapters"][name] = {**key, "items": kept[o]}
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
