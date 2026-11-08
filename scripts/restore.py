"""The restore stage: install a repository's locked dependencies into its working copy, if allowed.

A restore entry matches a lockfile at the repository root, or, with `nested`, in any project folder (not vendored or generated
ones). Commands run through sandbox.run (hygiene rules, timeout) with the project folder as the working directory.
A command word may hold `{js_tools}` (the folder of the shipped Node tools, installed on first use) or `{pnpm_store}`.
"""
from __future__ import annotations

import functools
import re
from pathlib import Path

import config
import gather
import js_tools
import sandbox

AUTH_FAILURE = re.compile(r"\b(401|403)\b|E401|E403|Unauthori[sz]ed|authentication (failed|required)|could not authenticate|NU1301", re.I)


def _lock_folders(tree, lockfile: str, nested: bool) -> list[str]:
    if not nested:
        return [""] if lockfile in tree else []
    suffix = "/" + lockfile
    folders = [""] if lockfile in tree else []
    folders += sorted(p[:-len(suffix)] for p in tree if p.endswith(suffix) and gather.noise_reason(p[:-len(suffix)] + "/x") is None)
    return folders


def _is_berry(checkout, folder: str) -> bool:
    if checkout is None:
        return False
    try:
        return "__metadata:" in (Path(checkout) / folder / "yarn.lock").read_text(errors="replace")
    except OSError:
        return False


def plans(tree, tools: dict, checkout=None) -> list[dict]:
    out = []
    for r in tools["restore"]:
        for folder in _lock_folders(tree, r["lockfile"], bool(r.get("nested"))):
            command = r["berry_command"] if r.get("berry_command") and _is_berry(checkout, folder) else r["command"]
            out.append({"ecosystem": r["ecosystem"], "lockfile": f"{folder}/{r['lockfile']}" if folder else r["lockfile"],
                        "command": list(command), "enabled": r["enabled"], "dir": folder, "auth": r.get("auth", r["ecosystem"])})
    return out


def restored(results: list[dict]) -> dict:
    """{ecosystem: True} only when every plan of that ecosystem ran and succeeded."""
    out: dict = {}
    for r in results:
        if r["status"] != "skipped":
            out[r["ecosystem"]] = out.get(r["ecosystem"], True) and r["status"] == "ok"
    return out


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
    results, tools_folder = [], None
    for p in plans:
        eco, folder = p["ecosystem"], p.get("dir", "")
        base = {"ecosystem": eco, "command": p["command"], "seconds": 0.0, "env_names": [], "log": None, "dir": folder}
        where = f" (in {folder})" if folder else ""
        if not p["enabled"]:
            results.append({**base, "status": "skipped",
                            "reason": f"Installing {eco} dependencies arrives in a later version of dossier."})
            continue
        command = list(p["command"])
        if any("{js_tools}" in word for word in command):
            try:
                if tools_folder is None:
                    tools_folder = js_tools.ensure_installed(functools.partial(sandbox.run, area=Path(area), parent=parent),
                                                             Path(area).parent, timeout)
            except js_tools.ToolError as e:
                results.append({**base, "status": "failed", "reason": f"Installing {eco} dependencies failed because its package manager "
                                                                      f"could not be installed: {e}{where}"})
                continue
        command = [w.replace("{js_tools}", str(tools_folder)).replace("{pnpm_store}", str(Path(area) / "cache" / "pnpm")) for w in command]
        r = sandbox.run(command, area=Path(area), cwd=Path(checkout) / folder, stage="restore-" + eco, timeout=timeout,
                        profile="restricted", ecosystem=p.get("auth", eco), parent=parent)
        base.update(seconds=r.seconds, env_names=r.env_names, log=str(r.stderr))
        if r.timed_out:
            results.append({**base, "status": "failed",
                            "reason": f"Installing {eco} dependencies took longer than {timeout} seconds and was stopped.{where}"})
        elif r.returncode == 0:
            results.append({**base, "status": "ok", "reason": None})
        else:
            err = r.stderr.read_text(errors="replace") if r.stderr.exists() else ""
            if AUTH_FAILURE.search(err):
                auth = p.get("auth", eco)
                reason = (f"Installing {eco} dependencies failed because the package registry refused the credentials. "
                          f"Add the variables or files it needs to registry_auth.{auth} in {config.path()}.{where}")
            else:
                reason = f"Installing {eco} dependencies failed (exit {r.returncode}). See {r.stderr}.{where}"
            results.append({**base, "status": "failed", "reason": reason})
    return results
