"""The restore stage: install a repository's locked dependencies into its working copy, if allowed.

Lockfiles at the repository root only. Commands run through sandbox.run (hygiene rules, timeout).
"""
from __future__ import annotations

import re
from pathlib import Path

import config
import sandbox

AUTH_FAILURE = re.compile(r"\b(401|403)\b|E401|E403|Unauthori[sz]ed|authentication (failed|required)|could not authenticate|NU1301", re.I)


def plans(tree, tools: dict) -> list[dict]:
    return [{"ecosystem": r["ecosystem"], "lockfile": r["lockfile"], "command": list(r["command"]), "enabled": r["enabled"]}
            for r in tools["restore"] if r["lockfile"] in tree]


def decide(plans, *, state, answer, no_restore, trust, allow_ref) -> dict:
    def out(action, reason=None, store=None):
        return {"action": action, "reason": reason, "store": store}

    if not plans:
        return out("skip", "There is no lockfile at the top of the repository, and dossier installs only from lockfiles.")
    if no_restore:
        return out("skip", "Installing dependencies was turned off with --no-restore.")
    if not trust["trusted"] and not allow_ref:
        return out("skip", f"{trust['why'][0].upper()}{trust['why'][1:]}, so dependencies were not installed. "
                           "Use --allow-ref to install them anyway.")
    declined = "You chose not to install dependencies for this repository."
    if answer:
        return out("run", store="yes") if answer == "yes" else out("skip", declined, store="no")
    stored = state.get("restore") or {}
    if stored.get("answer") == "no":
        return out("skip", declined + " Run prepare with --restore yes to change this.")
    if stored.get("answer") == "yes" and {p["ecosystem"] for p in plans} <= set(stored.get("ecosystems", [])):
        return out("run")
    return out("ask")


def run(plans, *, area, checkout, timeout, parent=None) -> list[dict]:
    results = []
    for p in plans:
        eco = p["ecosystem"]
        base = {"ecosystem": eco, "command": p["command"], "seconds": 0.0, "env_names": [], "log": None}
        if not p["enabled"]:
            results.append({**base, "status": "skipped",
                            "reason": f"Installing {eco} dependencies arrives in a later version of dossier."})
            continue
        r = sandbox.run(p["command"], area=Path(area), cwd=Path(checkout), stage="restore-" + eco, timeout=timeout,
                        profile="restricted", ecosystem=eco, parent=parent)
        base.update(seconds=r.seconds, env_names=r.env_names, log=str(r.stderr))
        if r.timed_out:
            results.append({**base, "status": "failed",
                            "reason": f"Installing {eco} dependencies took longer than {timeout} seconds and was stopped."})
        elif r.returncode == 0:
            results.append({**base, "status": "ok", "reason": None})
        else:
            err = r.stderr.read_text(errors="replace") if r.stderr.exists() else ""
            if AUTH_FAILURE.search(err):
                reason = (f"Installing {eco} dependencies failed because the package registry refused the credentials. "
                          f"Add the variables or files it needs to registry_auth.{eco} in {config.path()}.")
            else:
                reason = f"Installing {eco} dependencies failed (exit {r.returncode}). See {r.stderr}."
            results.append({**base, "status": "failed", "reason": reason})
    return results
