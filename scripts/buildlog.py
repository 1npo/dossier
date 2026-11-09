"""build.json: the crash-safe record of what each step of a build did. Standard library only.

Written only by the scripts (prepare, render, check_page). Claude never edits it.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

FILE, PREV = "build.json", "build.prev.json"
STEPS = ("pin", "tools", "copy", "measure", "extract", "read", "write", "check", "gaps", "render")
STATUSES = ("ok", "skipped", "failed", "reused")
WRITERS = ("prepare", "render", "check_page", "verify")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def start(out: Path, *, repo: str, sha: str, ref: str, version: str, options: dict) -> Path:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / FILE
    if path.exists():
        os.replace(path, out / PREV)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    _write(path, {"schema": 1, "build_id": f"{stamp}-{sha[:7]}", "dossier_version": version, "repo": repo,
                  "sha": sha, "ref": ref, "options": options, "records": []})
    return path


def load(path_or_out) -> dict | None:
    p = Path(path_or_out)
    if p.is_dir():
        p = p / FILE
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


UNMERGED_CODES = {"UU", "AA", "DD", "AU", "UA", "DU", "UD"}


def skill_state(root) -> dict:
    """Which skill code is running: its folder, git commit, whether it has uncommitted edits, whether a merge is unresolved.

    The values are None when `root` is not inside a git work tree.
    """
    root = str(root)
    git = ["git", "-C", root]
    head = subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True, text=True)
    if head.returncode != 0:
        return {"path": root, "commit": None, "dirty": None, "unmerged": None}
    status = subprocess.run(git + ["status", "--porcelain", "--", "."], capture_output=True, text=True).stdout.splitlines()
    return {"path": root, "commit": head.stdout.strip(), "dirty": bool(status),
            "unmerged": any(line[:2] in UNMERGED_CODES for line in status)}


def check_record(rec: dict) -> None:
    if rec.get("step") not in STEPS:
        raise ValueError(f"unknown step {rec.get('step')!r}")
    if rec.get("status") not in STATUSES:
        raise ValueError(f"unknown status {rec.get('status')!r}")
    if rec.get("by") not in WRITERS:
        raise ValueError(f"unknown writer {rec.get('by')!r}")
    if rec["status"] in ("skipped", "failed") and not rec.get("reason"):
        raise ValueError(f"step {rec['step']!r} is {rec['status']} but has no reason")


def append(path: Path, rec: dict) -> dict:
    path = Path(path)
    t = now()
    rec.setdefault("started", t)
    rec.setdefault("ended", t)
    rec.setdefault("seconds", 0.0)
    rec.setdefault("reason", None)
    check_record(rec)
    build = load(path)
    if build is None:
        raise FileNotFoundError(f"{path} does not exist; call start() first")
    build["records"].append(rec)
    _write(path, build)
    return rec


@contextmanager
def step(path: Path, step: str, part: str | None = None, by: str = "prepare"):
    rec: dict = {"step": step, "by": by, "status": "ok", "started": now()}
    if part:
        rec["part"] = part
    t0 = time.monotonic()
    try:
        yield rec
    except BaseException as e:
        rec["status"] = "failed"
        rec["reason"] = (str(e).splitlines() or [type(e).__name__])[0] or type(e).__name__
        rec["ended"], rec["seconds"] = now(), round(time.monotonic() - t0, 1)
        append(path, rec)
        raise
    rec["ended"], rec["seconds"] = now(), round(time.monotonic() - t0, 1)
    append(path, rec)


_ANY = object()


def latest(build: dict, step: str, part=_ANY) -> dict | None:
    for r in reversed(build["records"]):
        if r["step"] == step and (part is _ANY or r.get("part") == part):
            return r
    return None


def records(build: dict, step: str) -> list[dict]:
    return [r for r in build["records"] if r["step"] == step]


def record_browser(path, problems: int, diagrams_checked: int) -> dict:
    """Append the result of the real-browser check (written by check_page.py --record)."""
    return append(Path(path), {"step": "check", "part": "browser", "by": "check_page",
                               "status": "ok" if not problems else "failed",
                               "reason": None if not problems else f"{problems} problems in the browser check.",
                               "counts": {"problems": problems, "diagrams_checked": diagrams_checked}})
