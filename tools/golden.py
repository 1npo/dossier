#!/usr/bin/env python3
"""Capture dossier output from two copies of the skill and prove it is the same (plan 014, D14).

  python3 tools/golden.py repos OUT --from SKILL_DIR
  python3 tools/golden.py capture --skill DIR --repos REPOS --out OUT --set fast|full [--clones SRC] [--run RUN]
  python3 tools/golden.py compare A B [--review FILE]

`repos` builds the fixture repositories once, with fixed commit dates, so both sides read the same commits.
`capture` builds every case with one copy of the skill and keeps what it wrote. `compare` masks both captures
and prints `SAME` (exit 0) or the first lines of each difference (exit 1).

Standard library only. The fixture and page builders need pytest and pygments, so they run in a subprocess
under `uv run --with pytest --with pygments`.

"The same" means equal after these masks, and nothing else may differ:

| Mask                                                   | Where             | Why                                            |
|--------------------------------------------------------|-------------------|------------------------------------------------|
| `started`, `ended`, `seconds`, `date`, `generated_at`, | JSON files        | times of the run                               |
|   `checked_at` values                                  |                   |                                                |
| build-time stamps and `local_stamp` text               | HTML              | times of the run                               |
| `skill` objects and the process card's skill line      | build.json, HTML  | each side runs from its own folder and commit  |
| the `code` key of each adapter section                 | extract/*.json    | the skill code digest changes with any edit    |
| the skill folder's path                                | every file        | the two sides run from different folders       |
| the bodies of the three `dossier-gatherer/*` files and | HTML              | the page embeds the skill's own gather, deps   |
|   `data-a`/`data-b` on elements whose `data-view`      |                   |   and history modules; their import block may  |
|   starts with `dossier-gatherer/`                      |                   |   change. Their unmasked diff goes to --review |

Plus the masks the determinism run (the base captured twice) added, each with its reason (EXTRA_MASKS):

| the time prefix of `build_id` (the short sha is kept)  | build*.json       | the id is stamped with the build's start time  |
| `data-built="<ISO time>"` on the portfolio cards       | index.html        | the time the dossier was built                 |

A mask is never added to make a refactor diff disappear.
"""
from __future__ import annotations

import argparse
import difflib
import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

GIT_DATE = "2026-01-01T12:00:00+00:00"
DEFAULT_RUN = Path.home() / ".cache" / "dossier-refactor" / "run"
MASK = "<masked>"
DIFF_LINES = 60

# The fast set: (case, builder in tests/conftest.py or tests/support/repos.py, folder it creates).
FIXTURES = (
    ("pyrepo", "build_py_repo", "pyrepo"),
    ("jsrepo", "build_js_repo", "jsrepo"),
    ("csrepo", "build_cs_repo", "csrepo"),
    ("pylib", "build_pylib_repo", "pylib"),
    ("pyfastapi", "build_fastapi_repo", "pyfastapi"),
    ("cscake", "build_cake_repo", "cscake"),
    ("mixedsub", "build_mixed_pysub_repo", "mixedsub"),
)
# The synthetic pages: (case, module, function).
PAGES = (
    ("m3_page", "m3_page", "make"),
    ("m4_page", "m4_page", "make"),
    ("m5_page", "m5_page", "make"),
    ("m6_page", "m6_page", "make"),
    ("m6_page_small", "m6_page", "make_small"),
)
# The full set: public pinned clones under --clones (plan 014, block S).
CLONES = ("to", "bp", "rw")

TIME_KEYS = {"started", "ended", "seconds", "date", "generated_at", "checked_at"}
SKILL_KEY = "skill"
CODE_KEY = "code"
BUILD_RECORD_KEYS = ("step", "part", "status", "counts", "reason", "details")
GATHERER_PREFIX = "dossier-gatherer/"

# Masks the determinism run (the base captured twice) showed were needed. Each entry: (where, what, why).
EXTRA_MASKS: tuple[tuple[str, str, str], ...] = (
    ("build.json, build.prev.json", "the time prefix of `build_id` (`20261111T214259Z-<short sha>`; the sha is kept)",
     "the id is stamped with the build's start time"),
    ("HTML", '`data-built="<ISO time>"` on the portfolio cards (index.html)', "the time the dossier was built"),
)
BUILD_ID_RE = re.compile(r"^\d{8}T\d{6}Z(?=-)")
DATA_BUILT_RE = re.compile(r'\bdata-built="[^"]*"')

STAMP_RE = re.compile(r"\b\d{4}-\d{2}-\d{2} \d{2}:\d{2} [AP]M\b|\b\d{2}:\d{2} [AP]M\b")
SKILL_LINE_RE = re.compile(r"(Skill(?:</dt><dd>|: ))[0-9a-f]{7}(?:, uncommitted changes)?(?:, UNMERGED)?")
GATHERER_TAG_RE = re.compile(r'<[^<>]*\bdata-view="' + re.escape(GATHERER_PREFIX) + r'[^"]*"[^<>]*>')
LINE_ATTR_RE = re.compile(r'\bdata-([ab])="\d+"')
CODE_DATA_RE = re.compile(r'(<script type="application/json" id="code-data">)(.*?)(</script>)', re.S)
TAG_RE = re.compile(r"<[^>]*>")


# ---------------------------------------------------------------- masks


def mask_paths(text: str, skill_paths) -> str:
    """Replace each skill folder path (longest first) with `<SKILL>`."""
    for p in sorted({str(p) for p in skill_paths if p}, key=len, reverse=True):
        text = text.replace(p, "<SKILL>")
    return text


def mask_json(obj, *, extract: bool = False):
    """A copy of `obj` with time values and `skill` objects masked; in an extract file also each `code` key."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in TIME_KEYS or (k == SKILL_KEY and isinstance(v, dict)) or (extract and k == CODE_KEY):
                out[k] = MASK
            else:
                out[k] = mask_json(v, extract=extract)
        return out
    if isinstance(obj, list):
        return [mask_json(v, extract=extract) for v in obj]
    return obj


def reduce_build(obj):
    """build.json with each record reduced to step, part, status, counts, reason and details, then masked."""
    if isinstance(obj, dict) and isinstance(obj.get("records"), list):
        obj = {**obj, "records": [{k: r[k] for k in BUILD_RECORD_KEYS if k in r} for r in obj["records"]]}
    if isinstance(obj, dict) and isinstance(obj.get("build_id"), str):
        obj = {**obj, "build_id": BUILD_ID_RE.sub(MASK, obj["build_id"])}
    return mask_json(obj)


def _code_text(entry) -> list[str]:
    """The plain text of an embedded code-viewer entry (its lines are highlighted HTML)."""
    return [html.unescape(TAG_RE.sub("", line)) for line in entry.get("lines", [])]


def mask_html(text: str):
    """(masked page, {gatherer path: plain-text lines}) for one page."""
    bodies = {}

    def code(m):
        try:
            data = json.loads(m.group(2))
        except ValueError:
            return m.group(0)
        for path in sorted(data):
            if path.startswith(GATHERER_PREFIX):
                entry = data[path]
                bodies[path] = [f"(start {entry.get('start')}, total {entry.get('total')})", *_code_text(entry)]
                data[path] = MASK
        return m.group(1) + json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + m.group(3)

    text = CODE_DATA_RE.sub(code, text)
    text = GATHERER_TAG_RE.sub(lambda m: LINE_ATTR_RE.sub(lambda a: f'data-{a.group(1)}="{MASK}"', m.group(0)), text)
    text = STAMP_RE.sub(MASK, text)
    text = DATA_BUILT_RE.sub(f'data-built="{MASK}"', text)
    text = SKILL_LINE_RE.sub(lambda m: m.group(1) + MASK, text)
    return text, bodies


def canonical(path: Path, rel: str, skill_paths):
    """(comparable text, gatherer bodies) of one captured file."""
    raw = mask_paths(path.read_text(errors="replace"), skill_paths)
    if rel.endswith(".json"):
        try:
            obj = json.loads(raw)
        except ValueError:
            return raw, {}
        name = rel.rsplit("/", 1)[-1]
        if name in ("build.json", "build.prev.json"):
            obj = reduce_build(obj)
        else:
            obj = mask_json(obj, extract="/extract/" in f"/{rel}")
        return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n", {}
    if rel.endswith(".html"):
        return mask_html(raw)
    return raw, {}


# ---------------------------------------------------------------- repos


def _builders_dir(skill: Path) -> tuple[Path, str]:
    support = skill / "tests" / "support" / "repos.py"
    return (support.parent, "repos") if support.is_file() else (skill / "tests", "conftest")


def _git_env() -> dict:
    return {**os.environ, "GIT_AUTHOR_DATE": GIT_DATE, "GIT_COMMITTER_DATE": GIT_DATE, "DOSSIER_OFFLINE": "1",
            "PYTHONDONTWRITEBYTECODE": "1"}


def _py(code: str, *, cwd: Path, env: dict) -> subprocess.CompletedProcess:
    cmd = ["uv", "run", "-q", "--no-project", "--with", "pytest", "--with", "pygments", "python", "-c", code]
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)


def cmd_repos(a) -> int:
    out, skill = Path(a.out).resolve(), Path(a.from_).resolve()
    if out.exists() and any(out.iterdir()):
        sys.exit(f"golden: {out} is not empty")
    out.mkdir(parents=True, exist_ok=True)
    folder, module = _builders_dir(skill)
    calls = "\n".join(f"print(m.{fn}(out).sha)" for _, fn, _ in FIXTURES)
    code = f"import sys; from pathlib import Path\nsys.path.insert(0, {str(folder)!r})\nimport {module} as m\nout = Path({str(out)!r})\n{calls}\n"
    done = _py(code, cwd=out, env=_git_env())
    if done.returncode != 0:
        sys.exit(f"golden: building the fixture repositories failed:\n{done.stderr[-2000:]}")
    for (case, _, _), sha in zip(FIXTURES, done.stdout.split(), strict=True):
        print(f"{case} {sha}")
    return 0


# ---------------------------------------------------------------- capture


def _case_env(run: Path) -> dict:
    return {**_git_env(), "DOSSIER_HOME": str(run / "home"), "DOSSIER_CONFIG": str(run / "cfg.json"),
            "DOSSIER_CACHE": str(run / "cache")}


def _fresh(run: Path) -> Path:
    if run.exists():
        shutil.rmtree(run)
    run.mkdir(parents=True)
    return run


def _keep(src: Path, dest: Path) -> None:
    """Copy what a case wrote (its dossier home) into the capture."""
    if src.is_dir():
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__"))


def _log(dest: Path, name: str, done: subprocess.CompletedProcess) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"{name}.log").write_text(f"exit {done.returncode}\n--- stdout\n{done.stdout[-4000:]}\n--- stderr\n{done.stderr[-4000:]}\n")


def capture_repo(skill: Path, repo: Path, case: str, run: Path, out: Path, prepare_flags: list[str]) -> dict:
    run = _fresh(run / case)
    env = _case_env(run)
    launcher = str(skill / "scripts" / "dossier.py")
    codes = {}
    for step, args in (("prepare", ["prepare", str(repo), *prepare_flags]), ("render", ["render", str(repo), "--allow-errors"])):
        done = subprocess.run(["uv", "run", "-q", launcher, *args], cwd=run, env=env, capture_output=True, text=True)
        codes[step] = done.returncode
        _log(out / "logs" / case, step, done)
    _keep(run / "home", out / case)
    return codes


def capture_page(skill: Path, case: str, module: str, fn: str, run: Path, out: Path) -> dict:
    run = _fresh(run / case)
    support = skill / "tests" / "support"
    folder = support if (support / f"{module}.py").is_file() else skill / "tests" / "tools"
    code = (f"import sys; from pathlib import Path\nsys.path.insert(0, {str(folder)!r})\nimport {module}\n"
            f"print({module}.{fn}(Path({str(run)!r})))\n")
    done = _py(code, cwd=run, env=_git_env())
    _log(out / "logs" / case, "make", done)
    _keep(run / "home", out / case)
    return {"make": done.returncode}


def cmd_capture(a) -> int:
    skill, repos, out, run = (Path(p).resolve() for p in (a.skill, a.repos, a.out, a.run))
    if out.exists() and any(out.iterdir()):
        sys.exit(f"golden: {out} is not empty")
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"skill": str(skill), "set": a.set, "cases": {}}
    if a.set == "fast":
        for case, _, folder in FIXTURES:
            manifest["cases"][case] = capture_repo(skill, repos / folder, case, run, out, ["--full", "--no-restore", "--allow-missing"])
            print(case, manifest["cases"][case], flush=True)
        for case, module, fn in PAGES:
            manifest["cases"][case] = capture_page(skill, case, module, fn, run, out)
            print(case, manifest["cases"][case], flush=True)
    else:
        if not a.clones:
            sys.exit("golden: --set full needs --clones")
        for case in CLONES:
            manifest["cases"][case] = capture_repo(skill, Path(a.clones).resolve() / case, case, run, out, ["--full", "--no-restore"])
            print(case, manifest["cases"][case], flush=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return 0


# ---------------------------------------------------------------- compare


def _files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def compare(a: Path, b: Path, review: Path | None = None, out=sys.stdout) -> bool:
    """Print `SAME <case>` or the differences per case; write the gatherer review diff; True if all are the same."""
    ma, mb = (json.loads((x / "manifest.json").read_text()) for x in (a, b))
    skills = [ma.get("skill"), mb.get("skill")]
    same = True
    reviews = []
    for case in sorted(set(ma["cases"]) | set(mb["cases"])):
        problems = []
        ca, cb = ma["cases"].get(case), mb["cases"].get(case)
        if ca != cb:
            problems.append(f"exit codes differ: {ca} != {cb}")
        fa = _files(a / case) if (a / case).is_dir() else set()
        fb = _files(b / case) if (b / case).is_dir() else set()
        for rel in sorted(fa ^ fb):
            problems.append(f"only in {'A' if rel in fa else 'B'}: {rel}")
        for rel in sorted(fa & fb):
            ta, ga = canonical(a / case / rel, rel, skills)
            tb, gb = canonical(b / case / rel, rel, skills)
            for path in sorted(set(ga) | set(gb)):
                d = list(difflib.unified_diff(ga.get(path, []), gb.get(path, []), f"A/{case}/{path}", f"B/{case}/{path}", lineterm="", n=1))
                if d:
                    reviews.append(f"### {case} {rel}\n" + "\n".join(d))
            if ta != tb:
                d = list(difflib.unified_diff(ta.splitlines(), tb.splitlines(), f"A/{case}/{rel}", f"B/{case}/{rel}", lineterm="", n=1))
                problems.append(f"differs: {rel}\n" + "\n".join(_short(line) for line in d[:DIFF_LINES]))
        if problems:
            same = False
            print(f"DIFF {case}", file=out)
            for p in problems:
                print("  " + p.replace("\n", "\n    "), file=out)
        else:
            print(f"SAME {case}", file=out)
    review = review or (b / "gatherer-review.diff")
    review.write_text("\n\n".join(reviews) + ("\n" if reviews else ""))
    print("SAME" if same else "DIFFERENT", file=out)
    return same


def _short(line: str, width: int = 300) -> str:
    return line if len(line) <= width else line[:width] + " ..."


def cmd_compare(a) -> int:
    return 0 if compare(Path(a.a), Path(a.b), Path(a.review) if a.review else None) else 1


# ---------------------------------------------------------------- main


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="golden.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(required=True)
    r = sub.add_parser("repos", help="build the fixture repositories with fixed commit dates")
    r.add_argument("out")
    r.add_argument("--from", dest="from_", required=True, help="the skill folder whose test builders to use")
    r.set_defaults(fn=cmd_repos)
    c = sub.add_parser("capture", help="build every case with one copy of the skill")
    c.add_argument("--skill", required=True)
    c.add_argument("--repos", required=True)
    c.add_argument("--out", required=True)
    c.add_argument("--set", choices=("fast", "full"), required=True)
    c.add_argument("--clones")
    c.add_argument("--run", default=str(DEFAULT_RUN), help="the fixed work folder (the same on both sides)")
    c.set_defaults(fn=cmd_capture)
    m = sub.add_parser("compare", help="mask two captures and compare them")
    m.add_argument("a")
    m.add_argument("b")
    m.add_argument("--review")
    m.set_defaults(fn=cmd_compare)
    return p


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
