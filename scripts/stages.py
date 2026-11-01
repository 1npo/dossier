"""The stages of `prepare` that run before the measuring: pin, tools, copy (checkout and restore) and extract.

Each stage appends a record to build.json. A stage that cannot go on raises Stop, which carries the exit code
and the JSON that `prepare` prints.
"""
from __future__ import annotations

import functools
import subprocess
import time
from dataclasses import dataclass
from datetime import date

import adapters
import buildlog
import config
import restore
import sandbox
import shared_tools
import toolcheck
import workarea


@dataclass
class Options:
    ref: str = "HEAD"
    allow_missing: bool = False
    no_restore: bool = False
    allow_ref: bool = False
    submodules: bool = False
    restore: str | None = None
    full: bool = False


class Stop(Exception):
    def __init__(self, code: int, payload: dict):
        super().__init__(payload.get("stopped", "stopped"))
        self.code, self.payload = code, payload


class PrepareError(Exception):
    """A problem the user should read about; prepare prints it and exits 1."""


def record(build, t0, step, part=None, status="ok", reason=None, **extra) -> dict:
    rec = {"step": step, "by": "prepare", "status": status, "reason": reason,
           "started": buildlog.now(), "ended": buildlog.now(), "seconds": round(time.monotonic() - t0, 1), **extra}
    if part:
        rec["part"] = part
    return buildlog.append(build, rec)


def resolve_ref(top: str, ref: str) -> str:
    r = subprocess.run(["git", "-C", top, "rev-parse", "--verify", "--quiet", ref + "^{commit}"], capture_output=True, text=True)
    if r.returncode:
        raise PrepareError(f"'{ref}' is not a commit in this repository.")
    return r.stdout.strip()


def tree_at(top: str, sha: str) -> frozenset:
    out = subprocess.run(["git", "-C", top, "ls-tree", "-r", "--name-only", "-z", sha], capture_output=True).stdout
    return frozenset(p for p in out.decode("utf-8", "replace").split("\0") if p)


def stage_pin(build, top, ref, sha) -> dict:
    t0 = time.monotonic()
    trust = workarea.trusted(top, sha)
    record(build, t0, "pin", details={"sha": sha, "ref": ref, "branch_or_ref": ref, "trust": trust})
    return {"sha": sha, "short": sha[:7], "trust": trust}


def stage_tools(build, top, sha, opts: Options) -> dict:
    t0 = time.monotonic()
    langs = toolcheck.languages_at(top, sha)
    report = toolcheck.preflight(langs)
    found = [{"name": h["id"], "version": h["version"]} for h in report["host"] if h["version"]]
    bad = [h for h in report["host"] if h["status"] != "ok"]
    if report["missing"] and not opts.allow_missing:
        names = ", ".join(report["missing"])
        record(build, t0, "tools", status="failed", reason=f"Missing: {names}.", tools=found, details=report)
        raise Stop(2, {"stopped": "missing_tools",
                       "missing": [{k: h[k] for k in ("id", "status", "needs", "for", "install")} for h in bad],
                       "text": toolcheck.format_text(report),
                       "how_to_continue": "Install the missing tools, or run prepare again with --allow-missing."})
    details = dict(report)
    if report["missing"]:
        details.update(allowed_missing=True)
    record(build, t0, "tools", tools=found, details=details)
    return report


def restore_fields(results: list) -> dict:
    """The build.json fields that summarise restore.run results (also used by the hygiene tests)."""
    failed = [r for r in results if r["status"] == "failed"]
    ran = [r for r in results if r["status"] != "skipped"]
    status = "failed" if failed else "ok" if ran else "skipped"
    reason = " ".join(r["reason"] for r in (failed or results) if r["reason"]) if status != "ok" else None
    names = sorted({n for r in results for n in r["env_names"]})
    fields = {"status": status, "reason": reason, "counts": {"ecosystems": len(results)},
              "details": {"ecosystems": [{k: r[k] for k in ("ecosystem", "status", "reason", "seconds", "log")}
                                         | {"command": " ".join(r["command"])} for r in results]}}
    if names:
        fields.update(env_names=names, command=next(r["command"] for r in results if r["env_names"]))
    return fields


def stage_copy(build, top, sha, area, state, opts: Options, tree, trust) -> dict:
    t0 = time.monotonic()
    try:
        info = workarea.ensure_checkout(area, top, sha, opts.submodules)
    except workarea.CheckoutError as e:
        record(build, t0, "copy", "checkout", status="failed", reason=str(e))
        raise Stop(4, {"stopped": "checkout_failed", "reason": str(e)})
    record(build, t0, "copy", "checkout", details={k: info[k] for k in ("path", "created", "verified", "submodules", "submodules_on")})

    t0 = time.monotonic()
    plans = restore.plans(tree, toolcheck.load_tools())
    d = restore.decide(plans, state=state, answer=opts.restore, no_restore=opts.no_restore, trust=trust, allow_ref=opts.allow_ref)
    if d["store"]:
        state["restore"] = {"answer": d["store"], "date": date.today().isoformat(), "ecosystems": [p["ecosystem"] for p in plans]}
    restored: dict = {}
    if d["action"] == "skip":
        record(build, t0, "copy", "restore", status="skipped", reason=d["reason"],
               details={"planned": [p["ecosystem"] for p in plans]})
        results = []
    elif d["action"] == "ask":
        record(build, t0, "copy", "restore", status="skipped", reason="Waiting for your answer about installing dependencies.",
               details={"planned": [p["ecosystem"] for p in plans]})
        raise Stop(3, {"stopped": "restore_question",
                       "will_run": [{"ecosystem": p["ecosystem"], "command": " ".join(p["command"]), "where": info["path"],
                                     "note": "Installing can run the project's own build code on this machine, with your user rights."}
                                    for p in plans if p["enabled"]],
                       "how_to_answer": "Run prepare again with --restore yes or --restore no."})
    else:
        results = restore.run(plans, area=area, checkout=info["path"], timeout=config.timeouts()["restore"])
        record(build, t0, "copy", "restore", **restore_fields(results))
        restored = {r["ecosystem"]: r["status"] == "ok" for r in results if r["status"] != "skipped"}
    return {"checkout": info, "restore": results, "restore_decision": d, "restored": restored}


def stage_extract(build, top, sha, area, out, langs, trust, opts: Options, restored, tree, checkout) -> dict:
    t0 = time.monotonic()
    tools = toolcheck.load_tools()
    versions = {t["id"]: t["version"] for t in tools["tools"] if t["version"]}
    timeouts = config.timeouts()
    tool_run = functools.partial(sandbox.run, area=area, cwd=checkout, timeout=timeouts["tool"])
    rec = adapters.run_extract(
        adapters=adapters.detect(langs), checkout=checkout, sha=sha, tree=tree, area=area, out=out, trusted=trust,
        allow_ref=opts.allow_ref, restored=restored, treesitter=shared_tools.TreeSitter(tool_run),
        semgrep=shared_tools.Semgrep(tool_run), tool_versions=versions, timeout=timeouts["extract"])
    record(build, t0, "extract", **rec)
    return rec
