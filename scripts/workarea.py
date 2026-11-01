"""The per-repository working area: a verified clean checkout at the pinned commit, plus the trusted-ref check.

The working area is regenerable. The dossier itself lives in the output folder and is never touched here.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import config

DROP_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY")


class CheckoutError(RuntimeError):
    pass


def git(cwd, *args, check=True) -> str:
    env = {k: v for k, v in os.environ.items() if k not in DROP_ENV}
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, env=env)
    if check and r.returncode:
        last = ((r.stderr or r.stdout).strip().splitlines() or [""])[-1]
        raise CheckoutError(f"git {' '.join(args[:2])} failed: {last}"[:300])
    return r.stdout if r.returncode == 0 else ""


def _ok(cwd, *args) -> bool:
    env = {k: v for k, v in os.environ.items() if k not in DROP_ENV}
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, env=env).returncode == 0


def area_for(name: str, top: str, root_commit: str, cache_root: Path | None = None) -> Path:
    area = Path(cache_root or config.cache_root()) / name
    owner = area / "owner.json"
    if owner.exists():
        o = json.loads(owner.read_text(encoding="utf-8"))
        if o.get("repo") != top or o.get("root_commit") != root_commit:
            raise CheckoutError(f"The working area {area} belongs to {o.get('repo')}, not {top}. "
                                "Run clean for the other repository, or choose another cache_dir.")
        return area
    area.mkdir(parents=True, exist_ok=True)
    owner.write_text(json.dumps({"repo": top, "root_commit": root_commit}, indent=1) + "\n", encoding="utf-8")
    return area


def _submodules(top: str, sha: str) -> list[str]:
    out = git(top, "ls-tree", "-r", sha)
    return sorted(l.split("\t", 1)[1] for l in out.splitlines() if l.split(" ", 2)[1] == "commit")


def verify(checkout: Path, sha: str) -> tuple[bool, str]:
    head = git(checkout, "rev-parse", "HEAD", check=False).strip()
    if head != sha:
        return False, f"The copy is at {head[:10] or 'no commit'}, not {sha[:10]}."
    if git(checkout, "status", "--porcelain", "--untracked-files=no", "--ignore-submodules=all", check=False).strip():
        return False, "The copy has changes to tracked files."
    return True, ""


def ensure_checkout(area: Path, top: str, sha: str, submodules: bool = False) -> dict:
    co = Path(area) / "checkout"
    created = False

    def fresh():
        nonlocal created
        if co.exists():
            shutil.rmtree(co)
        git(area, "clone", "--local", "--no-checkout", "--quiet", top, str(co))
        created = True

    if not (co / ".git").exists() or git(co, "config", "--get", "remote.origin.url", check=False).strip() != top:
        fresh()
    else:
        git(co, "fetch", "--quiet", "--no-tags", "origin", "+refs/heads/*:refs/remotes/origin/*", check=False)
    if not _ok(co, "cat-file", "-e", sha + "^{commit}"):
        fresh()
    git(co, "checkout", "--quiet", "--detach", "--force", sha)
    git(co, "clean", "-ffdq")
    subs = _submodules(top, sha)
    if submodules and subs:
        git(co, "submodule", "update", "--init", "--recursive", "--quiet")
    ok, why = verify(co, sha)
    if not ok:
        raise CheckoutError(why)
    return {"path": str(co), "created": created, "head": sha, "verified": True, "submodules": subs,
            "submodules_on": bool(submodules and subs)}


def trusted(top: str, sha: str) -> dict:
    tags = git(top, "tag", "--points-at", sha, check=False).split()
    if tags:
        return {"trusted": True, "why": f"tag {tags[0]}", "default_branch": None}
    candidates = []
    sym = git(top, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", check=False).strip()
    if sym:
        candidates.append(sym)
    candidates += ["refs/remotes/origin/main", "refs/remotes/origin/master", "refs/heads/main", "refs/heads/master"]
    ref = next((r for r in candidates if _ok(top, "show-ref", "--verify", "--quiet", r)), None)
    if not ref:
        return {"trusted": False, "why": "no default branch was found (origin/HEAD, main or master)", "default_branch": None}
    short = ref[len("refs/remotes/"):] if ref.startswith("refs/remotes/") else ref[len("refs/heads/"):]
    if git(top, "rev-parse", ref).strip() == sha:
        return {"trusted": True, "why": f"tip of the default branch {short}", "default_branch": short}
    if _ok(top, "merge-base", "--is-ancestor", sha, ref):
        return {"trusted": True, "why": f"reachable from the default branch {short}", "default_branch": short}
    return {"trusted": False, "why": f"not a tag and not on the default branch {short}", "default_branch": short}


def clean(area: Path, cache_root: Path) -> bool:
    area = Path(area)
    if area.parent.resolve() != Path(cache_root).resolve() or area.name in ("", ".", "..", ".dossier-tools"):
        raise CheckoutError(f"Refusing to remove {area}: it is not a working area inside {cache_root}.")
    if not area.exists():
        return False
    shutil.rmtree(area)
    return True
