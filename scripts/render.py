#!/usr/bin/env python3
"""Validate report files and render the self-contained HTML dossier.

Claude writes one JSON file per report (see prompts/reports.md). This module checks
the shape, resolves every citation against the pinned commit, and fills a fixed
layout, so every dossier looks and reads the same.
"""
from __future__ import annotations

import fnmatch
import html
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import deps as depscan
import gather
import viewer
from gather import Repo

ROOT = Path(__file__).resolve().parent.parent
ASSETS, VENDOR = ROOT / "assets", ROOT / "vendor"

REPORTS = [  # id, title, written by Claude?
    ("dossier", "This dossier", False), ("overview", "This repository", True), ("capabilities", "Capabilities", True),
    ("interfaces", "Interfaces", True), ("architecture", "Architecture", True), ("domain-logic", "Domain logic", True),
    ("data", "Data model", True), ("code-tour", "Code tour", True),
    ("failures", "Failure modes", True), ("delivery", "Delivery, config and secrets", True),
    ("contributors", "Contributors", True), ("risks", "Risks", True),
    ("gaps", "Gaps", True), ("corrections", "Corrections", False),
]
TITLES = {r: t for r, t, _ in REPORTS}
CONF = ("confirmed", "inferred", "unknown")
BLOCKS = ("text", "table", "diagram", "list")
SHADE_KEY = '<p class="shade-key"><span class="fact"><i></i>Measured from the repository</span><span class="llm"><i></i>Written by Claude: facts mixed with cited, inferred and unknown statements</span></p>'
BARE_REPORTS = ("risks", "gaps", "corrections")   # tracker pages: no executive summary or contents card
GAP_KINDS = ("assumption", "unknown", "inference", "coverage")
SEVERITIES = ("critical", "high", "medium", "low", "info")
RISK_COLUMNS = ("ID", "Risk", "Category", "Severity")
FACT_KEYS = {k: f"facts-{k}" for k in ("git", "languages", "hot_files", "manifests", "env_vars",
                                       "secret_signals", "contributors", "ownership", "areas", "file_activity", "knowledge", "dependencies", "chunks")}
FACT_KEYS["areas"] = "facts-contributors"   # the areas are no longer drawn on the page
FACT_KEYS["hot_files"] = FACT_KEYS["manifests"] = "facts-git"   # their cards were retired; the figures still back statements about the repository
FACT_KEYS["chunks"] = "dossier-build"
FACT_KEYS["inventory"] = "facts-git"  # retired file-name inventory; old reports may still cite it
OPTIONAL_REPORTS = ("domain-logic",)  # reports added after v0.1: a dossier built before them still renders
DIAGRAM_START = re.compile(r"^\s*(%%\{.*?\}%%\s*)?(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram(-v2)?|erDiagram|journey|gantt|pie|mindmap|timeline|gitGraph|quadrantChart|requirementDiagram|C4\w+|sankey-beta|xychart-beta|block-beta|architecture-beta)\b", re.S)
INLINE_CITE = re.compile(r"\[\[(.+?)\]\]")
GATHERER_PATH = "dossier-gatherer/gather.py"   # the gatherer's source, embedded in the code viewer under this name
DEPS_PATH = "dossier-gatherer/deps.py"         # likewise the dependency analysis, which the Dependencies card cites
# What each "measured facts: <key>" citation means: (what it is, how the gatherer measured it, first line of its code, line that ends it)
FACT_INFO = {
    "git": ("Commit history", "Totals and timelines from the repository's commit history: commits, merges, first and last commit, commits per day and month, release tags, and who made them. Everything is counted by the gatherer, not written by Claude.",
            r"# ---- history pass", r"# ---- assemble contributor"),
    "languages": ("Languages", "How much of the code is written in each language, in non-blank lines. Files are classified by extension, and by content when the extension is ambiguous. Generated, vendored, lock and binary files are left out.",
                  r"# ---- languages", r"own = ownership\("),
    "hot_files": ("Most changed files", "The files that appear in the most commits, with how many lines changed in them and who changed them most. Files that no longer exist at the pinned commit are not listed.",
                  r"^    hot = \[\]", r"^    tags = \[\]"),
    "manifests": ("Project manifests", "Package manifests such as pyproject.toml or package.json, read for the project name, version and dependencies. Values that are template placeholders are ignored.",
                  r"^def _dep\(", r"# -+ areas"),
    "env_vars": ("Environment variables", "Reads of environment variables found by pattern matching in the source. Names built at run time are missed.",
                 r"^    env_refs, secret_hits", r"# ---- areas"),
    "secret_signals": ("Secret scan", "Strings shaped like credentials, and tracked files that often hold secrets. These are pattern matches only: the values are never stored, and each match needs a person to review it.",
                       r"^def sensitive_verdict\(", r"^def noise_reason\("),
    "contributors": ("Contributors", "Every author in the history, with identities merged when they share an email address or a full name, and classified as human, agent or bot from names, emails and commit-message markers. The classification is a heuristic.",
                     r"# ---- identities", r"# ---- history pass"),
    "ownership": ("Code ownership", "Who wrote the lines that exist today. The gatherer runs git blame on each file at the pinned commit and credits every surviving line to the author of its last change.",
                  r"^def blame_file\(", r"^ACTIVITY_CAP"),
    "areas": ("Areas", "The directories the code is grouped into. Large directories are split one or two levels deeper. Each area gets its commit counts, authors and activity dates.",
              r"# -+ areas", r"# -+ chunk planning"),
    "file_activity": ("Files changed by each contributor", "For every commit, the files it touched and how many lines it added and deleted, totalled per contributor and per day. Merge commits add nothing, and bulk commits (imports, reformatting) and vendored, generated and lock files are left out.",
                      r"# ---- history pass", r"# ---- assemble contributor"),
    "knowledge": ("Contributor knowledge map", "Who knows which files, from three measures per file: the lines that survive at the pinned commit (git blame), the commits that touched it, and the commits that touched it in the year before the pinned commit's date. A renamed file keeps its earlier history. Bots are left out, as are bulk commits (imports, reformatting) and vendored, generated, lock and binary files. Whether someone has left is an inference from their last commit.",
                  r"^# -+ knowledge map", r"^def collect\("),
    "dependencies": ("Dependencies", "The packages the repository declares in its manifests (Python, JavaScript and TypeScript, C#, shell) and the files that import them. Each import is matched to a declared package, so import names that differ from package names are mapped by a built-in table; the standard library and the repository's own code are not dependencies. Test files are told apart by path and file name. Versions and packages installed come from a lockfile when there is one. Categories come from a fixed list of known packages, and anything else is Other, which is an inference. Symbols used are counted from named imports and the members used on an imported name; for C# they are the distinct namespaces imported. Packages that only configure tools (linters, bundlers, test plugins) are not reported as unused.",
                     r"^def analyze\(", r'^            "deps": deps, "unused": unused', "deps"),
    "chunks": ("Reading coverage", "How the repository was divided up for reading: file sizes are estimated in tokens (bytes divided by 3.5) and packed into chunks that fit one context window.",
               r"# -+ chunk planning", r"# -+ main collection"),
}
FACT_INFO["inventory"] = FACT_INFO["git"]
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

# --------------------------------------------------------------------------- citations


def parse_cite(raw):
    raw = raw.strip()
    if raw.startswith("commit:"):
        sha = raw[7:].strip().lower()
        return {"kind": "commit", "sha": sha, "key": f"commit:{sha}", "text": f"commit {sha[:10]}"}
    if raw.startswith("facts:"):
        k = raw[6:].strip()
        return {"kind": "facts", "name": k, "key": f"facts:{k}", "text": f"measured facts: {k}"}
    m = re.match(r"^(.+?)(?::(\d+)(?:-(\d+))?)?$", re.sub(r"^(\./|/)+", "", raw))
    path, a, b = m.group(1), m.group(2), m.group(3)
    a, b = (int(a) if a else None), (int(b) if b else (int(a) if a else None))
    key = path + (f":{a}-{b}" if a and b and b != a else f":{a}" if a else "")
    return {"kind": "file", "path": path, "a": a, "b": b, "key": key, "text": key}


@lru_cache(maxsize=None)
def gatherer_source(which="gather"):
    return viewer.split_lines(Path((depscan if which == "deps" else gather).__file__).read_bytes())


def gatherer_path(key):
    """The name the code viewer knows the gatherer code behind a fact by."""
    return DEPS_PATH if len(FACT_INFO.get(key, ())) > 4 else GATHERER_PATH


@lru_cache(maxsize=None)
def gatherer_range(key):
    """(first, last) line of the gatherer code that measures a fact, or None."""
    info = FACT_INFO.get(key)
    if not info:
        return None
    lines = gatherer_source("deps" if len(info) > 4 else "gather")
    first = next((i for i, l in enumerate(lines) if re.search(info[2], l)), None)
    last = next((i for i in range((first or 0) + 1, len(lines)) if re.search(info[3], lines[i])), None)
    if first is None or last is None:
        return None
    while last > first + 1 and not lines[last - 1].strip():
        last -= 1
    return first + 1, last


class Cites:
    """Resolves citations against the pinned commit and builds their links."""

    def __init__(self, facts):
        self.facts = facts
        self.sha = facts["repo"]["sha"]
        self.repo = Repo(facts["repo"]["path"])
        self.remote = gather.remote_info((facts["repo"]["remote"] or {}).get("url"))
        self.status = {}          # key -> {"ok": bool, "msg": str, "type": str}
        self._lines = {}
        self._tree = None
        self._src = {}            # path -> (lines or None, reason): what the viewer may embed
        self.ranges = {}          # path -> cited (a, b) ranges, or None for no line numbers; recorded while pages are built
        self.windows = None       # path -> (first, last) lines embedded; None until the pages have been built once
        self.opens = {}           # citation key -> whether its marker opens the viewer, as of the latest page build
        self.dropped = []         # files left out of the viewer to keep the page small
        self._secret = None

    def tree(self):
        """(files, directories) at the pinned commit."""
        if self._tree is None:
            files = set(self.repo.git("ls-tree", "-r", "--name-only", self.sha).splitlines())
            dirs = {"/".join(p.split("/")[:i]) for p in files for i in range(1, len(p.split("/")))}
            self._tree = (files, dirs)
        return self._tree

    def path_like(self, text):
        """True when a table cell is exactly one path, directory or glob that exists at the pinned commit."""
        v = str(text or "").strip()
        if not v or re.search(r"[\s`<>\[\]()|,;]", v) or v.startswith("*"):
            return False
        core = v.rstrip("/")
        files, dirs = self.tree()
        if "*" in core or "?" in core:
            return any(fnmatch.fnmatchcase(p, core) for p in files)
        return core in files or core in dirs

    def check(self, c):
        k = c["key"]
        if k in self.status:
            return self.status[k]
        st = {"ok": True, "msg": "", "type": c["kind"]}
        if c["kind"] == "facts":
            if c["name"] not in FACT_KEYS:
                st.update(ok=False, msg=f"unknown facts key (use one of: {', '.join(FACT_KEYS)})")
        elif c["kind"] == "commit":
            ok = bool(re.fullmatch(r"[0-9a-f]{7,40}", c["sha"])) and subprocess.run(
                ["git", "-C", self.repo.path, "merge-base", "--is-ancestor", c["sha"], self.sha], capture_output=True).returncode == 0
            if not ok:
                st.update(ok=False, msg="not a commit in the history of the pinned commit")
        else:
            got = self.repo.read(f"{self.sha}:{c['path']}")
            if not got:
                st.update(ok=False, msg="no such path at the pinned commit")
            else:
                st["type"] = "tree" if got[0] == "tree" else "blob"
                if c["a"]:
                    if got[0] != "blob":
                        st.update(ok=False, msg="line numbers given for a directory")
                    else:
                        n = got[1].count(b"\n") + (1 if got[1] and not got[1].endswith(b"\n") else 0)
                        if c["a"] < 1 or c["b"] < c["a"] or c["b"] > n:
                            st.update(ok=False, msg=f"line range is outside the file, which has {n} lines")
        self.status[k] = st
        return st

    def secret_paths(self):
        """Files the gatherer flagged as holding secrets."""
        if self._secret is None:
            s = self.facts.get("secret_signals") or {}
            files = [x["path"] if isinstance(x, dict) else x for x in s.get("sensitive_files", [])]
            self._secret = set(files) | {h["path"] for h in s.get("hits", [])}
        return self._secret

    def source(self, path):
        """(lines, reason) for a file at the pinned commit. lines is None, and reason says why, when the viewer must not embed it.
        A secret-prone file is never read."""
        if path not in self._src:
            lines, reason = None, ""
            if path in self.secret_paths() or (gather.SENSITIVE_FILE.search(path) and not path.endswith(".pub")):
                reason = "may hold secrets"
            else:
                data = self.repo.read(f"{self.sha}:{path}")[1]
                if b"\0" in data[:8000]:
                    reason = "binary file"
                else:
                    lines = viewer.split_lines(data)
                    if not lines:
                        lines, reason = None, "empty file"
                    elif any(len(l) > viewer.MINIFIED_LINE for l in lines):
                        lines, reason = None, "minified file"
            self._src[path] = (lines, reason)
        return self._src[path]

    def viewable(self, c):
        """(ok, reason): whether a citation may open the code viewer."""
        if c["kind"] != "file":
            return False, "not a file"
        st = self.check(c)
        if not st["ok"]:
            return False, "unresolved"
        if st["type"] != "blob":
            return False, "directory"
        lines, reason = self.source(c["path"])
        return lines is not None, reason

    def view_attrs(self, c):
        """Attributes that make a citation open the viewer, or "" when it does not. While the first pass runs, it records the range."""
        attrs = self.view_markup(c)
        self.opens[c["key"]] = bool(attrs)
        return attrs

    def view_markup(self, c):
        if not self.viewable(c)[0]:
            return ""
        r = (c["a"], c["b"]) if c["a"] else None
        if self.windows is None:
            self.ranges.setdefault(c["path"], set()).add(r)
        elif c["path"] not in self.windows or not viewer.covers(self.windows[c["path"]], r):
            return ""
        a, b = viewer.clip(*r) if r else ("", "")
        return f' data-view="{E(c["path"])}" data-a="{a}" data-b="{b}"'

    def gatherer_view(self, c):
        """Attributes that point a measured-facts citation at the gatherer code that measured it, or "" when that code cannot be found."""
        rng = gatherer_range(c["name"])
        return f' data-view="{gatherer_path(c["name"])}" data-a="{rng[0]}" data-b="{rng[1]}"' if rng else ""

    def view_counts(self):
        """How many distinct citations open the viewer and how many do not, and how many files were left out for size."""
        n = sum(self.opens.values())
        return {"viewable": n, "not_viewable": len(self.opens) - n, "files_dropped_for_size": len(self.dropped)}

    def plan_view(self):
        """Pick the windows from the ranges the first pass recorded. Returns (dropped paths, whether any marker must be redrawn)."""
        files = {p: {"lines": self._src[p][0], "ranges": list(rs)} for p, rs in self.ranges.items()}
        self.windows, dropped = viewer.plan(files)
        self.dropped = dropped
        stale = bool(dropped) or any(not viewer.covers(self.windows[p], r) for p, rs in self.ranges.items() if p in self.windows for r in rs)
        return dropped, stale

    def url(self, c):
        if c["kind"] == "facts":
            return "#" + FACT_KEYS.get(c["name"], "")
        base, kind = self.remote.get("web_base"), self.remote.get("kind")
        if c["kind"] == "commit":
            if not base:
                return None
            return f"{base}/-/commit/{c['sha']}" if kind == "gitlab" else f"{base}/commits/{c['sha']}" if kind == "bitbucket" else f"{base}/commit/{c['sha']}"
        p, a, b = quote(c["path"]), c["a"], c["b"]
        is_dir = self.status.get(c["key"], {}).get("type") == "tree"
        if base and kind == "github":
            return f"{base}/{'tree' if is_dir else 'blob'}/{self.sha}/{p}" + (f"#L{a}-L{b}" if a else "")
        if base and kind == "gitlab":
            return f"{base}/-/{'tree' if is_dir else 'blob'}/{self.sha}/{p}" + (f"#L{a}-{b}" if a else "")
        if base and kind == "bitbucket":
            return f"{base}/src/{self.sha}/{p}" + (f"#lines-{a}:{b}" if a else "")
        return "file://" + quote(self.facts["repo"]["path"] + "/" + c["path"])


class Refs:
    """Numbered references for one report page."""

    def __init__(self, rid, cites):
        self.rid, self.cites, self.keys, self.parsed = rid, cites, [], {}

    def num(self, raw):
        c = parse_cite(raw)
        if c["key"] not in self.parsed:
            self.parsed[c["key"]] = c
            self.keys.append(c["key"])
        return self.keys.index(c["key"]) + 1

    def tip(self, c):
        if c["kind"] == "file" and self.cites.check(c)["type"] == "tree":
            return f"directory {c['path'].rstrip('/')}/, relative to the repo root"
        if c["kind"] == "facts" and c["name"] in FACT_INFO:
            return c["text"] + " (click to see what this is)"
        return c["text"]

    def mark(self, raws):
        out = []
        for raw in dict.fromkeys(raws):
            n = self.num(raw)
            c = parse_cite(raw)
            tip = E(self.tip(c))
            fact = f' data-fact="{E(c["name"])}"' if c["kind"] == "facts" and c["name"] in FACT_INFO else ""
            out.append(f'<a href="#ref-{self.rid}-{n}" data-tip="{tip}" aria-label="Source {n}: {tip}"{fact}{self.cites.view_attrs(c)}>[{n}]</a>')
        return f'<sup class="cite">{"".join(out)}</sup>' if out else ""

    def listing(self):
        if not self.keys:
            return '<p class="muted">This report cites no sources.</p>'
        rows = []
        for i, k in enumerate(self.keys, 1):
            c = self.parsed[k]
            st = self.cites.check(c)
            url = self.cites.url(c)
            view = self.cites.view_attrs(c)
            fact = c["kind"] == "facts" and c["name"] in FACT_INFO
            if fact:
                view = self.cites.gatherer_view(c)
            label = E(self.tip(c) if st["type"] == "tree" else c["text"])
            if not st["ok"]:
                link = f'<span class="bad">{label}</span> <span class="muted">unresolved: {E(st["msg"])}</span>'
            elif url and url.startswith("file://") and (view or st["type"] == "tree"):
                link = f"<code>{label}</code>"    # a local path would leak into a shared page
            elif url:
                ext = "" if c["kind"] == "facts" else ' target="_blank" rel="noopener noreferrer"'
                link = f'<a href="{E(url)}"{ext}>{label}</a>'
            else:
                link = f'<code>git show {E(c["sha"][:10])}</code>'
            kind = {"file": "file", "tree": "directory", "blob": "file", "commit": "commit", "facts": "measured by the gatherer"}.get(st["type"], "")
            btn = f' <button type="button" class="btn ref-btn" data-variant="outline" data-size="sm" data-open="{self.rid}-{i}">View code</button>' if view else ""
            if fact:
                btn = f' <button type="button" class="btn ref-btn" data-variant="outline" data-size="sm" data-fact="{E(c["name"])}">What is this?</button>' + btn
            rows.append(f'<li id="ref-{self.rid}-{i}"{view}>{link} <span class="muted">· {kind}</span>{btn}</li>')
        return "<ol class=\"refs\">" + "".join(rows) + "</ol>"


# --------------------------------------------------------------------------- text helpers


BARE_FILE = re.compile(r"(?<![\w/.\-])((?:[\w.\-]+/)*(?:[\w\-]+\.(?:sh|bash|zsh|py|js|mjs|ts|tsx|jsx|json|ya?ml|toml|ini|cfg|conf|md|go|rs|rb|java|kt|c|h|cpp|hpp|cs|php|sql|tf|html|css|txt|lock|mk|service|timer|socket|env|xml|gradle)|Makefile|Dockerfile|Justfile|Gemfile))(?![\w\-]|\.\w)")


def code_files(s):
    """Wrap bare file names in prose (install.sh, src/app.py) in <code>, leaving markup and existing code alone."""
    parts = re.split(r"(<code>.*?</code>|<[^>]+>)", s)
    return "".join(p if i % 2 else BARE_FILE.sub(r"<code>\1</code>", p) for i, p in enumerate(parts))


SEE_TAIL = re.compile(r"\bSee (\[\[[^\]]+\]\](?:(?:,| and|, and) \[\[[^\]]+\]\])*)\.?\s*$")


SENTENCE_START = re.compile(r"(^|[.!?:]\s+|\n\s*(?:[-*]\s+)?|^\s*[-*]\s+)$")
AFTER_PREP = re.compile(r"\b(?:in|at|from|to|into|of|by|via|see|under|inside|within|on|with|using|uses?|calls?|reads?|runs?|sources?|loads?|edits?|defined|set|handled|implemented|lives?|found)\s+$", re.I)
CLAUSE_WORD = re.compile(r"\s+(?!(?:and|or|but|which|while|so|then|because|where|when|as|if)\b)[A-Za-z0-9(`*]")


def stands_for_name(before, after):
    """True when a marker is used as the subject of a sentence ("[1] sets no strict mode") instead of ending a statement."""
    return bool(SENTENCE_START.search(before) or AFTER_PREP.search(before) or CLAUSE_WORD.match(after))


def inline(s, refs):
    """Escape and format one run of prose. [[path:1-9]] becomes a numbered source marker; [[path:1-9|name]] shows `name` first.
    A single file citation that stands where a file name belongs gets its path as the label, so a bare [3] never replaces a name."""
    s = SEE_TAIL.sub(r"\1", html.escape(str(s or ""), quote=False))  # a trailing "See [1]." is just the marker

    def cite_sub(m):
        raw, _, label = html.unescape(m.group(1)).partition("|")
        raws = [x.strip() for x in raw.split(", ") if x.strip()]
        label = label.strip()
        if not label and len(raws) == 1 and parse_cite(raws[0])["kind"] == "file" and stands_for_name(m.string[:m.start()], m.string[m.end():]):
            label = parse_cite(raws[0])["text"]
        mark = refs.mark(raws)
        return f"<code>{E(label)}</code>{mark}" if label else mark
    s = INLINE_CITE.sub(cite_sub, s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return code_files(re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s))


def md(text, refs):
    out = []
    for para in re.split(r"\n\s*\n", str(text or "").strip()):
        lines = [l for l in para.split("\n") if l.strip()]
        if lines and all(re.match(r"^\s*[-*] ", l) for l in lines):
            out.append("<ul>" + "".join(f"<li>{inline(re.sub(r'^\s*[-*] ', '', l), refs)}</li>" for l in lines) + "</ul>")
        elif lines and all(re.match(r"^\s*\d+[.)] ", l) for l in lines):
            out.append("<ol>" + "".join(f"<li>{inline(re.sub(r'^\s*\d+[.)] ', '', l), refs)}</li>" for l in lines) + "</ol>")
        elif lines:
            out.append("<p>" + inline(" ".join(l.strip() for l in lines), refs) + "</p>")
    return "".join(out)


def inline_cites(*texts):
    found = []
    for t in texts:
        for m in INLINE_CITE.finditer(str(t or "")):
            found += [x.strip() for x in m.group(1).partition("|")[0].split(", ") if x.strip()]
    return found


def new_cites(cite, *texts):
    """The sources in `cite` that the texts do not already mark inline, so a statement never shows one source twice."""
    seen = {parse_cite(x)["key"] for x in inline_cites(*texts)}
    return [x for x in dict.fromkeys(cite or []) if parse_cite(x)["key"] not in seen]


def badge(label, cls="", variant="outline"):
    return f'<span class="badge {cls}" data-variant="{variant}">{E(label)}</span>'


def basis(conf):
    return badge(conf, f"basis-{conf}", {"confirmed": "secondary", "inferred": "outline", "unknown": "destructive"}.get(conf, "outline"))


def basis_for(node):
    """The basis pill for a statement, taking the user's decision into account."""
    u = node.get("user")
    if u and u["action"] in ("confirm", "answer") and node.get("conf") == "confirmed":
        return badge("confirmed by you", "basis-confirmed", "secondary")
    if u and u["action"] == "wrong":
        return badge("disputed by you", "basis-unknown", "destructive")
    return basis(node.get("conf"))


def gid_tag(node):
    if node.get("gid") and (node.get("was") or node.get("user")):
        return f'<code class="gid" tabindex="0" data-tip="Use this ID with /dossier confirm" data-tip-kind="note">{E(node["gid"])}</code>'
    return ""


def user_note(u):
    if not u:
        return ""
    when = E(str(u.get("date", ""))[:10])
    text = f" {E(u['text'])}" if u.get("text") else ""
    if u["action"] == "confirm":
        return f'<div class="muted by-user">You confirmed this on {when}.{text}</div>'
    if u["action"] == "answer":
        return f'<div class="muted by-user">You answered on {when}:{text}</div>'
    return f'<div class="muted by-user">You said this is wrong on {when}:{text} The next build will rewrite it.</div>'


SEV_TONE = {"critical": "destructive", "high": "destructive", "medium": "primary", "low": "secondary", "info": "outline"}


def sev_badge(v):
    return badge(v, "", SEV_TONE.get(str(v).strip().lower(), "outline"))


STATUS_STYLE = {"implemented": ("basis-confirmed", "secondary"), "partial": ("basis-inferred", "outline"), "dead code": ("basis-unknown", "destructive")}
STATUSES = ("Implemented", "Partial", "Stubbed", "Planned", "Documented only", "Dead code")


def status_badge(v):
    cls, variant = STATUS_STYLE.get(str(v).strip().lower(), ("", "outline"))
    return badge(v, cls, variant)


def type_badge(t):
    return badge(t, "", {"human": "primary", "agent": "secondary", "bot": "outline"}[t])


def gap_badge(k):
    return badge(k, f"gap-{k}", {"unknown": "destructive", "assumption": "secondary"}.get(k, "outline"))


ICONS = {"warn": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
         "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>'}


def alert(text, title="Heads up", kind="warn", variant=None):
    v = f' data-variant="{variant}"' if variant else ""
    return (f'<div class="alert"{v}><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{ICONS[kind]}</svg><h2>{E(title)}</h2><section>{text}</section></div>')


def fmt(n):
    return f"{n:,}" if isinstance(n, int) else str(n)


# --------------------------------------------------------------------------- claims and validation


def claim(report, where, node, text, cells=None):
    cites = list(node.get("cite") or []) + inline_cites(text, *(cells or []))
    return {"report": report, "where": where, "conf": node.get("conf"), "cites": cites, "note": node.get("note"),
            "text": text, "node": node}


def claims_of(rid, rep):
    out = []
    for b in rep.get("blocks", []):
        where = b.get("heading") or ""
        t = b.get("type")
        if t == "text":
            out.append(claim(rid, where, b, b.get("text", "")))
        elif t == "diagram":
            out.append(claim(rid, where, b, b.get("title") or where or "Diagram"))
        elif t == "list":
            out += [claim(rid, where, it, it.get("text", "")) for it in b.get("items", []) if isinstance(it, dict)]
        elif t == "table":
            for r in b.get("rows", []):
                if isinstance(r, dict):
                    cells = [str(c) for c in r.get("cells", [])]
                    out.append(claim(rid, where, r, " · ".join(cells[:2]), cells))
    return out


def validate(reports, facts, cites, partial=False):
    errors, warnings = [], []
    words = lambda s: len(str(s or "").split())
    names = [r for r, _, w in REPORTS if w]
    for rid in names:
        rep = reports.get(rid)
        if rep is None:
            (warnings if partial or rid in OPTIONAL_REPORTS else errors).append(f"Report '{rid}' is missing (expected reports/{rid}.json).")
            continue
        if not isinstance(rep, dict):
            errors.append(f"Report '{rid}' must be a JSON object.")
            continue
        for key in ("headline", "summary"):
            if not str(rep.get(key) or "").strip():
                errors.append(f"Report '{rid}' needs a non-empty '{key}'.")
        if words(rep.get("headline")) > 40:
            warnings.append(f"Report '{rid}': the headline is long. Keep it to one sentence.")
        if words(rep.get("summary")) > 220:
            warnings.append(f"Report '{rid}': the summary is over 220 words. Executive summaries should be short.")
        if rid != "gaps" and not isinstance(rep.get("blocks"), list):
            errors.append(f"Report '{rid}' needs a 'blocks' list.")
            continue
        for i, b in enumerate(rep.get("blocks", [])):
            tag = f"Report '{rid}', block {i + 1}"
            if b.get("type") in BLOCKS and not str(b.get("heading") or "").strip():
                warnings.append(f"{tag}: add a 'heading'. The contents list names each card by it (the page will call this one '{block_title(b)}').")
            if b.get("type") not in BLOCKS:
                errors.append(f"{tag}: 'type' must be one of {', '.join(BLOCKS)}.")
            elif b["type"] == "table":
                cols = b.get("columns")
                if not isinstance(cols, list) or not cols:
                    errors.append(f"{tag}: a table needs 'columns'.")
                    continue
                if rid == "capabilities" and "Status" not in cols:
                    warnings.append(f"{tag}: add a 'Status' column ({', '.join(STATUSES)}) instead of ending the description with the status.")
                if rid == "risks":
                    missing = [c for c in RISK_COLUMNS if c not in cols]
                    if missing and any(c in cols for c in ("Risk", "Severity")):
                        errors.append(f"{tag}: risk tables must include the columns {', '.join(RISK_COLUMNS)} (missing: {', '.join(missing)}).")
                for j, r in enumerate(b.get("rows", [])):
                    if not isinstance(r, dict) or len(r.get("cells", [])) != len(cols):
                        errors.append(f"{tag}, row {j + 1}: each row must be an object whose 'cells' has {len(cols)} entries.")
            elif b["type"] == "diagram":
                src = b.get("mermaid", "")
                if not DIAGRAM_START.match(src):
                    errors.append(f"{tag}: 'mermaid' must start with a Mermaid diagram keyword such as flowchart, sequenceDiagram or erDiagram.")
            elif b["type"] == "list" and not isinstance(b.get("items"), list):
                errors.append(f"{tag}: a list needs 'items'.")
        if rid == "gaps":
            for j, it in enumerate(rep.get("items", [])):
                if it.get("kind") not in GAP_KINDS or not it.get("statement"):
                    errors.append(f"Report 'gaps', item {j + 1}: needs a 'statement' and a 'kind' of {', '.join(GAP_KINDS)}.")
        for c in claims_of(rid, rep):
            label = f"Report '{rid}'" + (f", '{c['where']}'" if c["where"] else "") + f", '{c['text'][:50]}'"
            if c["conf"] not in CONF:
                errors.append(f"{label}: 'conf' must be one of {', '.join(CONF)}.")
                continue
            if c["conf"] != "unknown" and not c["cites"]:
                errors.append(f"{label}: a {c['conf']} statement needs at least one citation.")
            if c["conf"] != "confirmed" and not c["note"]:
                warnings.append(f"{label}: add a 'note' saying what would confirm this.")
        # every citation must resolve
        raws = []
        for c in claims_of(rid, rep):
            raws += c["cites"]
        if rid == "gaps":
            for it in rep.get("items", []):
                raws += list(it.get("cite") or []) + inline_cites(it.get("statement"))
        for raw in dict.fromkeys(raws):
            c = parse_cite(raw)
            st = cites.check(c)
            if not st["ok"]:
                errors.append(f"Report '{rid}': citation '{raw}' does not resolve: {st['msg']}.")
        # file paths mentioned in backticks without a citation
        tree = None
        for c in claims_of(rid, rep):
            for span in re.findall(r"`([^`\s]+)`", c["text"]):
                if "/" in span or re.search(r"\.\w{1,5}$", span):
                    tree = tree if tree is not None else set(cites.repo.git("ls-tree", "-r", "--name-only", cites.sha).splitlines())
                    if span in tree and span not in {parse_cite(x)["path"] for x in c["cites"] if parse_cite(x)["kind"] == "file"}:
                        warnings.append(f"Report '{rid}': mentions `{span}` without citing it. Use [[{span}]] instead.")
    return errors, warnings


# --------------------------------------------------------------------------- block rendering


def provenance(node, refs, text="", label=""):
    """The basis pill, sources and note under a block. `text` is what the block says: sources it marks inline are not repeated."""
    conf = node.get("conf")
    note = node.get("note")
    note_html = f'<span class="muted"> {inline(note, refs)}</span>' if note and conf != "confirmed" else ""
    lbl = f'<span class="prov-label">{E(label)}</span>' if label else ""
    return f'<div class="prov">{lbl}{basis_for(node)}{gid_tag(node)}{refs.mark(new_cites(node.get("cite"), text))}{note_html}</div>{user_note(node.get("user"))}'


_NW = re.compile(r"\d{4}-\d{2}-\d{2}|[\w.]+(?:-[\w.]+)*\[bot\]|\b[A-Za-z]+-\d\w*")


def keep_whole(h):
    """Stop dates and bot names breaking at their hyphens (text outside tags only)."""
    return "".join(seg if seg.startswith("<") else _NW.sub(lambda m: f'<span class="nw">{m.group(0)}</span>', seg) for seg in re.split(r"(<[^>]*>)", h))


def cell_html(cell, refs):
    if refs.cites.path_like(cell):
        return f'<code>{E(str(cell).strip()).replace("/", "/<wbr>")}</code>'
    return keep_whole(inline(cell, refs))


def render_table(columns, rows, refs, tid, filterable=True, plain=False, group=None, foot=None, sort=True):
    """rows are dicts with cells/conf/cite/note (authored) or plain lists of ready HTML (measured)."""
    head = "".join(f"<th>{E(c)}</th>" for c in columns)
    if not plain:
        head += "<th>Basis</th><th>Sources</th>"
    body = []
    for r in rows:
        if plain:
            body.append("<tr>" + "".join(f'<td data-sort="{E(c[1])}">{keep_whole(str(c[0]))}</td>' if isinstance(c, tuple) else f"<td>{keep_whole(str(c))}</td>" for c in r) + "</tr>")
            continue
        tds = []
        for col, cell in zip(columns, r["cells"]):
            kind = col.strip().lower()
            tds.append(f"<td>{sev_badge(cell)}</td>" if kind == "severity" else f"<td>{status_badge(cell)}</td>" if kind == "status" else f"<td>{cell_html(cell, refs)}</td>")
        note = f'<div class="muted">{inline(r.get("note"), refs)}</div>' if r.get("note") and r.get("conf") != "confirmed" else ""
        cites_ = new_cites(r.get("cite"), *r["cells"])
        body.append("<tr>" + "".join(tds) + f'<td class="basis-cell">{basis_for(r)}{gid_tag(r)}{note}{user_note(r.get("user"))}</td><td>{refs.mark(cites_)}</td></tr>')
    flt = f'<input class="input tbl-filter" type="search" data-target="{tid}" placeholder="Filter rows" aria-label="Filter rows">' if filterable and len(rows) > 6 else ""
    top = ("<tr class=\"group-row\">" + "".join(f'<th colspan="{n}"{" class=\"grp\"" if lbl else ""}>{E(lbl)}</th>' for lbl, n in group) + "</tr>") if group else ""
    tf = f'<tfoot><tr class="total-row">{"".join(f"<td>{c}</td>" for c in foot)}</tr></tfoot>' if foot else ""
    return f'{flt}<div class="table-container"><table class="table" id="{tid}"{"" if sort else " data-nosort"}><thead>{top}<tr>{head}</tr></thead><tbody>{"".join(body)}</tbody>{tf}</table></div>'


def block_card(head, body, prov, extra="", action=""):
    h = f"<header><h3>{E(head)}</h3>{action}</header>" if head or action else ""
    return f'<div class="card block llm {extra}">{h}<section>{body}</section><footer>{prov}</footer></div>'


EXPAND_ICONS = ('<svg class="ic-max" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="m21 3-7 7"/><path d="m3 21 7-7"/></svg>'
                '<svg class="ic-min" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m14 10 7-7"/><path d="M20 10h-6V4"/><path d="m3 21 7-7"/><path d="M4 14h6v6"/></svg>')


def block_title(b):
    """The name a block's card goes by in the contents list: its heading, or one made from what it holds."""
    if b.get("heading"):
        return b["heading"]
    t = b.get("type")
    if t == "diagram":
        return b.get("title") or "Diagram"
    if t == "table":
        return ", ".join(str(c) for c in b.get("columns", [])[:3]) or "Table"
    if t == "list":
        return "Key points"
    plain = re.sub(r"\[\[[^\]]*\]\]|[`*]", "", str(b.get("text", "")))
    words = plain.split()
    return " ".join(words[:7]) + ("..." if len(words) > 7 else "") if words else "Details"


def render_block(b, refs, rid, idx, notes=None):
    t = b["type"]
    prov = provenance(b, refs, b.get("text", ""), "Diagram" if notes else "") if t in ("text", "diagram") else ""
    if t == "text":
        return block_card(block_title(b), md(b["text"], refs), prov)
    if t == "list":
        lis = "".join(f'<li>{inline(i["text"], refs)} {basis_for(i) if (i["conf"] != "confirmed" or i.get("user")) else ""}{gid_tag(i)}{refs.mark(new_cites(i.get("cite"), i["text"]))}'
                      + (f'<div class="muted">{inline(i.get("note"), refs)}</div>' if i.get("note") and i["conf"] != "confirmed" else "") + user_note(i.get("user")) + "</li>"
                      for i in b["items"])
        return f'<div class="card block llm"><header><h3>{E(block_title(b))}</h3></header><section><ul class="claims">{lis}</ul></section></div>'
    if t == "table":
        cap = f'<p class="muted">{inline(b["caption"], refs)}</p>' if b.get("caption") else ""
        h = f'<header><h3>{E(block_title(b))}</h3></header>'
        return f'<div class="card block llm">{h}<section>{cap}{render_table(b["columns"], b["rows"], refs, f"t-{rid}-{idx}")}</section></div>'
    src = b["mermaid"].strip()
    title = block_title(b)
    sub_ = f'<p>{E(b["title"])}</p>' if b.get("heading") and b.get("title") else ""
    return (f'<div class="card block llm diagram"><header><h3>{E(title)}</h3>{sub_}<div class="card-action"><button class="btn" data-variant="ghost" data-size="sm" type="button" data-expand title="Expand" aria-label="Expand diagram">{EXPAND_ICONS}</button></div></header>'
            f'<section><div class="mermaid-host" data-src="{E(src)}"><pre class="muted">Diagram loads when this report is opened.</pre></div>'
            f'{notes[0] if notes else ""}<details><summary class="muted">Diagram source</summary><pre>{E(src)}</pre></details></section><footer>{prov}{notes[1] if notes else ""}</footer></div>')


NOTES_HEAD = re.compile(r"^\s*notes?\s+(on|for)\b", re.I)


def render_blocks(blocks, refs, rid):
    """Render report blocks. A text block headed "Notes on ..." right after a diagram goes inside that diagram's card."""
    out, i = [], 0
    while i < len(blocks):
        b, nxt = blocks[i], blocks[i + 1] if i + 1 < len(blocks) else None
        if b["type"] == "diagram" and nxt and nxt["type"] == "text" and NOTES_HEAD.match(nxt.get("heading") or ""):
            notes = (f'<div class="diagram-notes"><h4>{E(nxt["heading"])}</h4>{md(nxt["text"], refs)}</div>', provenance(nxt, refs, nxt["text"], "Notes"))
            out.append(render_block(b, refs, rid, i, notes))
            i += 2
            continue
        out.append(render_block(b, refs, rid, i))
        i += 1
    return "".join(out)


# --------------------------------------------------------------------------- measured panels


def card(title, body, pid=None, desc=None, refs=None, cite=None, kind="fact"):
    """kind is "fact" for a card of figures measured from the repository, "llm" for one that holds statements written by Claude."""
    mark = refs.mark([cite] if isinstance(cite, str) else cite) if refs and cite else ""
    d = f"<p>{E(desc)}</p>" if desc else ""
    idattr = f' id="{pid}"' if pid else ""
    return f'<div class="card panel {kind}"{idattr}><header><h2>{E(title)} {mark}</h2>{d}</header><section>{body}</section></div>'


def path_cell(path, refs, line=None):
    ref = f"{path}:{line}" if line else path
    return f"<code>{E(ref).replace('/', '/<wbr>')}</code>{refs.mark([ref])}"


class Raw(str):
    """Markup that is already safe to place in the page."""


def stats_html(items):
    cols = 3 if len(items) == 6 else 4 if len(items) == 8 else min(len(items), 5)
    return f'<div class="stats" style="grid-template-columns:repeat({cols},minmax(0,1fr))">' + "".join(
        f'<div class="stat {extra[0] if extra else ""}"><div class="k">{k if isinstance(k, Raw) else E(k)}</div><div class="v">{v if isinstance(v, Raw) else E(v)}</div>{f'<div class="s">{E(s)}</div>' if s else ""}</div>' for k, v, s, *extra in items) + "</div>"


def fact_box(title, rows):
    """A titled box of label/value pairs; values are ready HTML."""
    return f'<div class="facts-group"><h3>{E(title)}</h3><dl class="facts">' + "".join(f"<dt>{E(k)}</dt><dd>{v}</dd>" for k, v in rows) + "</dl></div>"


def panel_git(f, refs, ctx):
    g, fl, r = f["git"], f["files"], f["repo"]
    stats = stats_html([
        ("Commits", fmt(g["commits"]), f"{fmt(g['merges'])} merges"),
        ("Active span", f"{(g['age_days'] / 365.25):.1f} years", f"{g['first_commit']} to {g['last_commit']}"),
        ("Tracked files", fmt(fl["tracked"]), f"{fmt(fl['tests'])} contain tests"),
        ("Code lines", fmt(fl["total_code_lines"]), f"{len([l for l in f['languages'] if l['kind'] == 'code'])} programming languages"),
    ])
    link = ctx["cites"].url({"kind": "commit", "sha": r["sha"]})
    sha = f'<a href="{E(link)}" target="_blank" rel="noopener noreferrer">{E(r["sha"])}</a>' if link else E(r["sha"])
    remote = ctx["cites"].remote
    url = remote.get("web_base") or remote.get("url")
    url_html = (f'<a href="{E(url)}" target="_blank" rel="noopener noreferrer">{E(url)}</a>' if url and url.startswith("http") else E(url)) if url else '<span class="muted">none configured</span>'
    m = main_manifest(f)
    unset = '<span class="muted">not stated</span>'
    repo_box = fact_box("Repository", [("Name", E(r["name"])), ("Branch", E(r["branch"] or r["ref"])), ("Remote URL", url_html),
                                       ("Pinned commit", sha + refs.mark(["commit:" + r["sha"]])), ("Commit date", E(r["commit_date"]))])
    proj_box = fact_box("Project", [("Name", E(real(m.get("name")) or "") or unset), ("Version", E(real(m.get("version")) or "") or unset), ("Author", E(real(m.get("author")) or "") or unset)])
    boxes = f'<div class="facts-groups">{repo_box}{proj_box}</div>'
    tags = g["tags"]

    def gap(i):
        if i + 1 >= len(tags): return "·"
        d = (datetime.strptime(tags[i]["date"], "%Y-%m-%d") - datetime.strptime(tags[i + 1]["date"], "%Y-%m-%d")).days
        return f"{d} days"
    rel = ""
    if tags:
        rows = "".join(f'<tr><td><code>{E(t["name"])}</code></td><td>{E(t["date"])}</td><td class="muted">{gap(i)}</td></tr>' for i, t in enumerate(tags[:10]))
        rel = f'<div class="activity solo"><div class="activity-side"><h3>Recent releases</h3><table class="table"><thead><tr><th>Tag</th><th>Date</th><th>Gap</th></tr></thead><tbody>{rows}</tbody></table></div></div>'
    notes = "".join(alert(E(w)) for w in f["repo"]["warnings"])
    return card("Overview", notes + stats + boxes + rel + languages_block(f, refs), "facts-git", refs=refs, cite="facts:git")


def languages_block(f, refs):
    langs = sorted(f["languages"], key=lambda l: -l["lines"])
    total = sum(l["lines"] for l in langs) or 1
    top, rest = langs[:7], langs[7:]
    items = [(l["name"], l["lines"]) for l in top] + ([("Other", sum(l["lines"] for l in rest))] if rest else [])
    segs = "".join(f'<i class="lang-{k + 1}" style="width:{max(0.8, 100 * v / total):.1f}%" title="{E(n)}: {100 * v / total:.1f}%"></i>' for k, (n, v) in enumerate(items))
    legend = "".join(f'<li><b class="lang-{k + 1}"></b>{E(n)} <span class="muted">{100 * v / total:.0f}%</span></li>' for k, (n, v) in enumerate(items))
    ex = f["files"]["excluded"]
    note = ("Not counted: " + ", ".join(f"{fmt(v)} {k}" for k, v in ex.items()) + " files. ") if ex else ""
    return (f'<div class="langs" id="facts-languages"><h3>Languages, by share of non-blank lines {refs.mark(["facts:languages"])}</h3><div class="lbar">{segs}</div>'
            f'<ul class="llegend">{legend}</ul>' + (f'<p class="muted">{E(note)}</p>' if note else "") + "</div>")



# --------------------------------------------------------------------------- dependencies card

DEP_CATEGORIES = depscan.CATEGORIES + ("Other",)
DEP_VIEWS = (("files", "By file"), ("table", "Ranked list"), ("matrix", "Module matrix"), ("tree", "Treemap"), ("bubble", "Reliance plot"), ("graph", "Module graph"))
DEP_MEASURES = (("breadth", "Breadth"), ("spread", "Spread"), ("depth", "Depth"))
DEP_SCOPES = (("all", "All"), ("runtime", "Runtime"), ("dev", "Dev"))
DEP_ZOOMS = (("1", "Top level"), ("2", "Modules"), ("3", "Folders"), ("99", "All files"))
DEP_SHOWS = (("all", "All paths"), ("touched", "Only paths it touches"))
DEP_START = {"view": "files", "measure": "breadth", "scope": "all", "zoom": "3", "show": "all"}   # what the card opens on; dossier.js starts from the same values


def dp_group(gid, label, options, hidden=False):
    on = DEP_START[gid]
    btns = "".join(f'<button type="button" class="btn" data-variant="outline" data-size="sm" data-v="{v}" aria-pressed="{"true" if v == on else "false"}">{E(t)}</button>' for v, t in options)
    return (f'<div class="dp-ctl" id="dp-{gid}-ctl"{" hidden" if hidden else ""}><span class="dp-lbl" id="dp-{gid}-l">{E(label)}</span>'
            f'<div class="button-group" id="dp-{gid}" role="group" aria-labelledby="dp-{gid}-l">{btns}</div></div>')


def dp_ver(v):
    return f' <span class="dp-ver">{E(v)}</span>' if v else ""


def dependency_findings(d):
    """One row per package for each of the three findings, as plain table cells (text and sort key)."""
    pkg = lambda n, v: (f'<code>{E(n)}</code>{dp_ver(v)}', n.lower())
    pill = lambda label, cls: badge(label, cls, "outline")
    scope = lambda s: (badge(s, "", "secondary") if s == "runtime" else badge(s, "", "outline"), s)
    rows = []
    for u in d["unused"]:
        rows.append([pkg(u["n"], u["v"]), pill("Declared, never imported", "dp-warn"), scope(u["s"]), E(u["note"])])
    for u in d["undeclared"]:
        mods = ", ".join(sorted(u["mods"]))
        via = f' · reaches you via {E(u["via"])}' if u["via"] else " · no declared package provides it"
        rows.append([pkg(u["n"], ""), pill("Imported, never declared", "dp-crit"), ('<span class="muted">·</span>', "~"),
                     f'{u["files"]} file{"" if u["files"] == 1 else "s"} in {E(mods)}{via}'])
    for x in d["deps"]:
        if x["s"] == "runtime" and x["src"] == 0:
            rows.append([pkg(x["n"], x["v"]), pill("Runtime, used only in tests", "dp-warn"), scope(x["s"]),
                         f'{x["tst"]} test file{"" if x["tst"] == 1 else "s"}, no source imports · likely belongs with the dev dependencies'])
    return rows


def panel_dependencies(f, refs):
    d = f.get("dependencies")
    if d is None and "dependencies" not in f:
        body = '<p class="muted">Dependencies were not recorded in this dossier. Run prepare again to include them.</p>'
    elif not d:
        body = '<p class="muted">No declared or imported dependencies were found in the languages this analysis reads (Python, JavaScript and TypeScript, C#, shell).</p>'
    elif d.get("error"):
        body = alert(E(d["error"]), "The dependency analysis failed")
    else:
        body = dependencies_card(d, refs)
    return card("Dependencies", body, "facts-dependencies", refs=refs, cite="facts:dependencies")


def dependencies_card(d, refs):
    deps, co = d["deps"], d.get("configOnly") or {"runtime": 0, "dev": 0}
    runtime = sum(1 for x in deps if x["s"] == "runtime") + sum(1 for x in d["unused"] if x["s"] == "runtime") + co["runtime"]
    total = len(deps) + len(d["unused"]) + co["runtime"] + co["dev"]
    test_only = sum(1 for x in deps if x["s"] == "runtime" and x["src"] == 0)
    split = (f'<div class="dp-split"><span class="rt"><i>runtime</i><b>{runtime}</b></span><span><i>dev</i><b>{total - runtime}</b></span></div>'
             f'<div class="dp-splitbar" aria-hidden="true"><i style="flex:{runtime}"></i><i class="dv" style="flex:{total - runtime}"></i></div>')
    zero = lambda n: "zero" if not n else ""
    tiles = stats_html([
        ("Declared", Raw(f'{total}{split}'), ""),
        ("Packages installed", d["transTotal"] if d.get("transTotal") else "·", "incl. transitive" if d.get("transTotal") else "no lockfile found"),
        ("Declared, never imported", len(d["unused"]), "", f"dp-warn {zero(len(d['unused']))}"),
        ("Imported, never declared", len(d["undeclared"]), "", f"dp-crit {zero(len(d['undeclared']))}"),
        ("Runtime, used only in tests", test_only, "", f"dp-warn {zero(test_only)}"),
    ])
    rows = dependency_findings(d)
    finds = (render_table(["Package", "Finding", "Scope", "Detail"], rows, refs, "t-dep-findings", False, True)
             if rows else '<p class="muted">No findings: every declared package is imported or used through configuration, and every import is declared.</p>')
    notes = ""
    if d.get("trimmed"):
        notes = alert(f'To keep the page small, {fmt(d["trimmed"])} files that import no declared package are left out of the By file view. Module totals still count them.', "Some files are not shown")
    controls = ('<div class="dp-controls">' + dp_group("view", "View", DEP_VIEWS) + dp_group("measure", "Rank by", DEP_MEASURES) + dp_group("scope", "Scope", DEP_SCOPES)
                + dp_group("zoom", "Zoom", DEP_ZOOMS, True) + dp_group("show", "Show", DEP_SHOWS, True)
                + '<div class="dp-ctl" id="dp-dep-ctl" hidden><label class="dp-lbl" for="dp-depsel">Dependency</label><div class="dp-combo">'
                  '<input id="dp-depsel" class="input dp-dsel" type="text" role="combobox" aria-expanded="false" aria-controls="dp-deplist" aria-autocomplete="list" autocomplete="off" spellcheck="false" placeholder="All dependencies">'
                  '<ul id="dp-deplist" class="dp-deplist" role="listbox" aria-label="Dependencies" hidden></ul></div></div></div>')
    foot = '<div class="dp-foot"><span><i class="dp-sw"></i>source files</span><span><i class="dp-sw t"></i>test files</span></div>'
    jsn = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return (f'<div class="dp" id="dp-root">{notes}{tiles}<div class="dp-finds">{finds}</div>{controls}<div id="dp-stage"></div>{foot}</div>'
            f'<script type="application/json" id="dp-data">{jsn}</script>')


def panel_env(f, refs):
    rows = [[f"<code>{E(e['name'])}</code>", fmt(e["count"]), path_cell(e["first"]["path"], refs, e["first"]["line"])] for e in f["env_vars"][:40]]
    body = render_table(["Variable", "References", "First seen"], rows, refs, "t-env", True, True) if rows else '<p class="muted">No environment variable reads were detected.</p>'
    more = f'<p class="muted">Showing 40 of {len(f["env_vars"])}.</p>' if len(f["env_vars"]) > 40 else ""
    return card("Environment variables read by the code", body + more, "facts-env_vars", "Detected with pattern matching, so dynamic names are missed.", refs, "facts:env_vars")


def panel_secrets(f, refs):
    s = f["secret_signals"]
    hits = [[E(h["kind"]), path_cell(h["path"], refs, h["line"])] for h in s["hits"][:50]]
    files = [[path_cell(x["path"], refs), E(x["verdict"])] if isinstance(x, dict) else [path_cell(x, refs), '<span class="muted">not inspected</span>'] for x in s["sensitive_files"][:30]]
    body = (render_table(["Pattern", "Location"], hits, refs, "t-sec", False, True) if hits else '<p>No credential-shaped strings were found.</p>')
    body += ("<h3>Tracked files that often hold secrets, and what they contain</h3>" + render_table(["File", "What the file contains"], files, refs, "t-sens", False, True)) if files else ""
    return card("Secret scan", body + f'<p class="muted">{E(s["note"])}</p>', "facts-secret_signals", refs=refs, cite="facts:secret_signals")


def type_cls(t):
    return {"human": "human", "agent": "agent", "bot": "bot"}[t]


PALETTE = 6  # people who get their own colour; everyone else shares grey


def owner_palette(f):
    """{id or name: colour class} for the biggest owners of today's code, so every graphic colours a person the same way."""
    o = f.get("ownership")
    people = o["people"] if o else f["contributors"]["people"]
    pal = {}
    for i, p in enumerate(people[:PALETTE]):
        cls = f"lang-{i + 1}"
        pal[p["name"]] = cls
        if p.get("id"):
            pal[p["id"]] = cls
    return pal


def share_bar(items, total):
    """The same bar and legend as the languages bar. Items are (class, name, value, note)."""
    segs = "".join(f'<i class="{c}" style="width:{max(0.8, 100 * v / total):.1f}%" title="{E(n)}: {100 * v / total:.1f}%"></i>' for c, n, v, _ in items if v)
    legend = "".join(f'<li><b class="{c}"></b>{E(n)} <span class="muted">{100 * v / total:.0f}%{E(note)}</span></li>' for c, n, v, note in items if v)
    return f'<div class="lbar">{segs}</div><ul class="llegend">{legend}</ul>'


# ---- commit calendar: colour is who made the commits, strength is how many, and the zoom buttons change the granularity
ZOOMS = ("Months", "Days", "Calendar")
START_ZOOM = 1   # the page opens on days
MIX = (0, 35, 55, 78, 100)  # percent of the person's colour at each level, the rest is the muted background


def day_cell(counts, peak, pal, title, cls="", style="", key=None):
    """One calendar cell. Several people on the same day share the cell as coloured stripes.
    The tooltip is built in the browser from the calendar data when the cell has a `key` (a day or a month), else it is `title`."""
    tip = f' data-cal="{E(key)}"' if key else f' data-tip="{E(title)}"'
    n = sum(counts.values())
    if not n:
        return f'<span class="cc {cls}" style="{style}"{tip}></span>'
    lvl = 1 + min(3, int(4 * (n - 1) / max(peak, 1)))
    mix = lambda cid: f"color-mix(in oklab, var({'--l' + pal[cid][5:] if cid in pal else '--l8'}) {MIX[lvl]}%, var(--muted))"
    by_col = {}
    for cid, c in counts.items():
        by_col[mix(cid)] = by_col.get(mix(cid), 0) + c
    parts = sorted(by_col.items(), key=lambda kv: -kv[1])
    if len(parts) == 1:
        bg = parts[0][0]
    else:
        acc, stops = 0.0, []
        for col, c in parts:
            stops.append(f"{col} {acc:.1f}% {acc + 100 * c / n:.1f}%")
            acc += 100 * c / n
        bg = f"linear-gradient(90deg,{','.join(stops)})"
    return f'<span class="cc on {cls}" style="{style}background:{bg}"{tip}></span>'


def calendar_data(f):
    """What the browser needs to build a calendar tooltip: who made how many commits, and added and deleted how many lines, on each day.
    One copy serves every calendar on the page."""
    g = f["git"]
    daily, lines = g.get("daily") or {}, g.get("daily_lines") or {}
    pal = owner_palette(f)
    names = {p["id"]: p["name"] for p in f["contributors"]["people"]}
    ids = {cid for who in daily.values() for cid in who}
    tags = defaultdict(list)
    for t in g.get("tags") or []:
        tags[t["date"]].append(t["name"])
    return {"people": {cid: [names.get(cid, "Others"), int(pal[cid][5:]) if cid in pal else 8] for cid in sorted(ids)},
            "days": {d: {cid: [n, *lines.get(d, {}).get(cid, (0, 0))] for cid, n in who.items()} for d, who in daily.items()},
            "tags": dict(tags), "lines": bool(lines)}


def contributor_legend(names, pal):
    items = sorted({v: k for k, v in pal.items() if k in names.values()}.items())
    return '<ul class="llegend">' + "".join(f'<li><b class="{cls}"></b>{E(n)}</li>' for cls, n in items) + '<li><b class="own-other"></b>Everyone else</li></ul>'


def calendar_html(g, names, pal, tags=()):
    daily = g.get("daily")
    if not daily:
        return '<p class="muted">The commit calendar needs the daily history. Run prepare again to include it.</p>'
    plural = lambda n: f"{n} commit{'' if n == 1 else 's'}"
    days = {datetime.strptime(d, "%Y-%m-%d").date(): c for d, c in daily.items()}
    end = max(days)
    tag_days = {t["date"] for t in tags}
    tag_months = {d[:7] for d in tag_days}
    # level 0: one cell per month
    months = defaultdict(Counter)
    for d, c in days.items():
        months[(d.year, d.month)].update(c)
    years = list(range(min(d.year for d in days), end.year + 1))[-16:]
    peak_m = max((sum(c.values()) for (y, _), c in months.items() if y in years), default=1)
    head = '<span></span>' + "".join(f'<span class="hh">{n}</span>' for n in "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()) + '<span class="hh">Total</span>'
    rows = ""
    for y in years:
        rows += f'<span class="hy">{y}</span>'
        for m in range(1, 13):
            k = f"{y}-{m:02d}"
            rows += day_cell(months.get((y, m), Counter()), peak_m, pal, "", "mc rel" if k in tag_months else "mc", key=k)
        rows += f'<span class="ht">{fmt(sum(sum(c.values()) for (yy, _), c in months.items() if yy == y))}</span>'
    lvl0 = f'<div class="heat">{head}{rows}</div>'
    peak_d = max(sum(c.values()) for c in days.values())

    def cell(d):
        return day_cell(Counter(days.get(d, {})), peak_d, pal, "", "rel" if d.isoformat() in tag_days else "", key=d.isoformat())
    blank = '<span class="cc ph"></span>'
    # level 1: a year per block, one boxed column per week (Monday first)
    blocks = ""
    for y in reversed(years):
        first, last = datetime(y, 1, 1).date(), datetime(y, 12, 31).date()
        wk, weeks = first - timedelta(days=first.weekday()), ""
        n_weeks = 0
        while wk <= last:
            weeks += '<div class="wk">' + "".join(cell(d) if first <= d <= last else blank for d in (wk + timedelta(days=i) for i in range(7))) + "</div>"
            wk, n_weeks = wk + timedelta(days=7), n_weeks + 1
        blocks += f'<div class="yr"><b class="hy">{y}</b><div class="weeks" style="--cols:{n_weeks}">{weeks}</div></div>'
    lvl1 = f'<div class="year-scroll">{blocks}</div>'
    # level 2: the last twelve months as month calendars, one boxed row per week
    cur, mcal = (end.replace(day=1) - timedelta(days=335)).replace(day=1), ""
    while cur <= end:
        nxt = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
        wk, weeks = cur - timedelta(days=cur.weekday()), ""
        while wk < nxt:
            weeks += '<div class="wk">' + "".join(cell(d) if cur <= d < nxt else blank for d in (wk + timedelta(days=i) for i in range(7))) + "</div>"
            wk += timedelta(days=7)
        mcal += f'<div class="mcal"><b>{cur.strftime("%b %Y")}</b><div class="days">{weeks}</div></div>'
        cur = nxt
    lvl2 = f'<div class="month-cals">{mcal}</div>'
    levels = "".join(f'<div class="zoom-lvl" data-zoom-level="{i}"{"" if i == START_ZOOM else " hidden"}>{html_}</div>' for i, html_ in enumerate((lvl0, lvl1, lvl2)))
    bar = ('<div class="zoom-bar"><span class="muted">Zoom</span>'
           f'<button type="button" class="btn" data-variant="outline" data-size="sm" data-zoom="-1" aria-label="Zoom out: fewer, larger periods" title="Zoom out"{" disabled" if START_ZOOM == 0 else ""}>&minus;</button>'
           f'<button type="button" class="btn" data-variant="outline" data-size="sm" data-zoom="1" aria-label="Zoom in: one cell per day" title="Zoom in"{" disabled" if START_ZOOM == len(ZOOMS) - 1 else ""}>+</button>'
           f'<span class="zoom-name" aria-live="polite" data-zoom-names="{E("|".join(ZOOMS))}">{ZOOMS[START_ZOOM]}</span></div>')
    swatches = "".join(f'<span class="cc sw" style="background:color-mix(in oklab, var(--l7) {m}%, var(--muted))"></span>' for m in MIX)
    key = (f'<div class="heat-key muted"><span class="kg">Fewer commits {swatches} More commits</span>'
           '<span class="kg">A cell split in stripes had several people commit in that period</span>'
           + ('<span class="kg"><span class="cc sw rel"></span> Release tag</span>' if tag_days else "") + '</div>')
    return f'<div class="zoomable" data-zoom-root data-zoom-start="{START_ZOOM}">{levels}{contributor_legend(names, pal)}<div class="cal-foot">{bar}{key}</div></div>'


def knowledge_palette(k, f):
    """The --l colour number (1 to 6) of each person on the knowledge map: the one owner_palette gives them elsewhere on the page, else the next free one."""
    pal = owner_palette(f)
    out, used = {}, set()
    for c in k["contributors"]:
        n = int(pal[c["id"]][5:]) if c["id"] in pal else 0
        if n and n not in used:
            out[c["id"]] = n
            used.add(n)
    free = iter([n for n in range(1, PALETTE + 1) if n not in used])
    return {c["id"]: out.get(c["id"]) or next(free) for c in k["contributors"]}


def compact(n):
    return f"{n / 1_000_000:.1f}M" if n >= 1_000_000 else f"{n / 1000:.1f}k" if n >= 1000 else str(n)


KM_MEASURES = (("lines", "Lines"), ("commits", "Commits"))
KM_VIEWS = (("full", "All paths"), ("mine", "Only paths they touched"))
KM_ZOOMS = (("1", "Top level"), ("2", "Modules"), ("3", "Folders"), ("99", "All files"))
KM_START = {"metric": "lines", "view": "full", "zoom": "2"}   # what the page opens on; dossier.js starts from the same values


def km_group(gid, label, options):
    on = KM_START[gid]
    btns = "".join(f'<button type="button" class="btn" data-variant="outline" data-size="sm" data-v="{v}" aria-pressed="{"true" if v == on else "false"}">{E(t)}</button>' for v, t in options)
    return f'<div class="km-ctl"><span class="muted" id="km-{gid}-l">{E(label)}</span><div class="button-group" id="km-{gid}" role="group" aria-labelledby="km-{gid}-l">{btns}</div></div>'


def knowledge_card(f):
    """Who knows which files: a tree with an ownership bar per row. Every share is worked out in the browser (dossier.js) from the embedded per-file figures."""
    k = f.get("knowledge")
    if not k:
        return '<p class="muted">The knowledge map was not recorded in this dossier. Run prepare again to include it.</p>'
    if not k["contributors"]:
        return '<p class="muted">No commits by people (as opposed to bots) touch the files in this repository, so there is nobody to map.</p>'
    cls = knowledge_palette(k, f)
    people = [{"name": c["name"], "short": c["short"], "commits": c["commits"], "last": c["last"], "departed": c["departed"], "cls": cls[c["id"]]} for c in k["contributors"]]
    others = {"name": "Others", "short": "Others", "people": k["others"]["people"], "commits": k["others"]["commits"], "cls": 8} if k["others"] else None
    data = {"head": f["repo"]["short"], "date": k["date"], "contributors": people, "others": others, "files": k["files"]}
    jsn = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    lines = sum(r[1] for r in k["files"])
    tiles = stats_html([("HEAD", Raw(f'<span class="mono">{E(f["repo"]["short"])}</span>'), f"committed {k['date']}"),
                        ("Contributors", fmt(len(people) + (others["people"] if others else 0)), "people, bots left out"),
                        ("Files", fmt(len(k["files"])), "text files at HEAD"),
                        ("Lines", compact(lines), "non-blank, surviving at HEAD")])
    notes = ""
    if k["approx_files"]:
        notes += alert(f'The line counts are estimates for {fmt(k["approx_files"])} of the {fmt(len(k["files"]) + k["trimmed"])} files, because git blame did not finish within its time limit. '
                       'For those files the gatherer used lines added minus lines deleted in each person\'s commits instead.', "Estimated line shares")
    if k["trimmed"]:
        notes += alert(f'To keep the page small, {fmt(k["trimmed"])} of the smallest and least changed files are left out of this map.', "Some files are not shown")
    controls = '<div class="km-controls">' + km_group("metric", "Measure", KM_MEASURES) + km_group("view", "Show", KM_VIEWS) + km_group("zoom", "Zoom", KM_ZOOMS) + "</div>"
    months = k["departed_months"]
    legend = (f'<div class="km-note"><span id="km-formula"></span><span><i class="km-hz"></i>Hatched = no longer active</span>'
              f'<span>{badge("at risk", "basis-inferred")} top contributor has left and holds 50% or more</span></div>')
    infer = (f'<p class="muted km-infer">{basis("inferred")} "No longer active" and "at risk" are inferences, not records. A person is treated as having left when they made no commit in the '
             f'{months} months before HEAD ({E(k["date"])}), and a folder is at risk when its top contributor has left and holds 50% or more. '
             'Someone on leave, or working in another repository, would be marked wrongly. The team can confirm who has really left.</p>')
    tree = ('<div class="km-tree"><div class="km-scroller" id="km-scroller" role="tree" aria-label="Repository tree with contributor familiarity">'
            '<div class="km-thead" role="presentation"><span>Path</span><span>Who knows it</span><span id="km-th3">Top contributor</span></div>'
            '<div class="km-rows" id="km-rows"></div></div>'
            '<div class="km-mini" id="km-mini-wrap" title="Minimap: click or drag to scroll"><canvas id="km-mini" aria-hidden="true"></canvas></div></div>')
    return (f'<div class="km" id="km-root">{notes}{tiles}{controls}<h3>Repository tree</h3>'
            f'<div class="km-chips" id="km-chips" role="group" aria-label="Contributor"></div>{tree}{legend}{infer}</div>'
            f'<script type="application/json" id="km-data">{jsn}</script>')


def panel_contributors(f, refs):
    g, c = f["git"], f["git"]["contributors"]
    cb = g["commits_by_type"]
    commits_total = sum(cb.values()) or 1
    o = f.get("ownership")
    pal = owner_palette(f)
    tiles = stats_html([(t.capitalize(), str(c[t]), f"{fmt(cb[t])} commit{'' if cb[t] == 1 else 's'} · {100 * cb[t] / commits_total:.0f}%") for t in ("human", "agent", "bot")])
    assisted = ""
    if g["agent_assisted_commits"]:
        by = ", ".join(f"{k}: {v}" for k, v in g["agent_assisted_by"].items())
        assisted = f'<p class="muted">{fmt(g["agent_assisted_commits"])} commits carry an AI-assistant marker ({E(by)}). They are counted under "agent" in the table below.</p>'
    # a bar of whose code it is, with its legend, above the contributor table
    if o:
        total = o["total_lines"]
        top = o["people"][:PALETTE]
        rest = total - sum(p["lines"] for p in top)
        people_items = [(pal[p["id"]], p["name"], p["lines"], "") for p in top] + [("lang-8", "Everyone else", rest, "")]
        who_bar = f'<div id="facts-ownership">{share_bar(people_items, total)}</div>'
    else:
        ppl = f["contributors"]["people"]
        top = ppl[:PALETTE]
        rest = commits_total - sum(p["commits"] for p in top)
        people_items = [(pal[p["id"]], p["name"], p["commits"], "") for p in top] + [("lang-8", "Everyone else", rest, "")]
        who_bar = f'{share_bar(people_items, commits_total)}<p class="muted">Code ownership was not measured in this dossier, so these bars show commits. Run prepare again to measure it.</p>'
    names = {p["id"]: p["name"] for p in f["contributors"]["people"]}
    own = {p["id"]: p for p in (o or {}).get("people", [])}
    rows = []
    for p in f["contributors"]["people"][:40]:
        lines = own.get(p["id"])
        who = f'<b class="own-dot {pal.get(p["id"], "own-other")}"></b>{E(p["name"])}'
        code = (f'{fmt(lines["lines"])} <span class="meter"><i class="{pal.get(p["id"], "own-other")}" style="width:{max(lines["share_pct"], 0.4):.1f}%"></i></span> {lines["share_pct"]}%', lines["lines"]) if lines else ("0" if o else "·", 0)
        added, deleted, months = p["added"], p["deleted"], max(p["active_months"], 1)
        mix = " · ".join(f"{v} {k}" for k, v in p["commits_by_type"].items() if v)
        rows.append([who, type_badge(p["type"]), (f'{fmt(p["commits"])} ({p["share_pct"]}%)', p["commits"]),
                     code, f'{p["first"]} to {p["last"]}', fmt(p["recent_commits_12m"]), fmt(p["assisted_commits"]),
                     (fmt(added), added), (fmt(deleted), deleted), (f"{added - deleted:+,}", added - deleted),
                     (fmt(round((added + deleted) / p["commits"])) if p["commits"] else "0", (added + deleted) / max(p["commits"], 1)),
                     fmt(p["active_months"]), (f"{p['commits'] / months:.1f}", p["commits"] / months), mix])
    more = f'<p class="muted">{f["contributors"]["not_listed"]} more contributors are in the gatherer data but not shown. The table shows the top 40.</p>' if f["contributors"]["not_listed"] or len(f["contributors"]["people"]) > 40 else ""
    table = render_table(["Name", "Type", "Commits", "Code today" if o else "Code today (not measured)", "Active", "Last 12 months", "Agent-assisted",
                          "Lines added", "Lines deleted", "Net lines", "Lines changed per commit", "Active months", "Commits per active month", "Commits by type"],
                         rows, refs, "t-people", True, True)
    main = card("Contributors", tiles + assisted + who_bar + "<h3>Detail by contributor</h3>" + table + more,
                "facts-contributors", None, refs, ["facts:contributors"] + (["facts:ownership"] if o else []))
    know = card("Contributor knowledge map", knowledge_card(f), "facts-knowledge",
                "Which parts of the repository each person knows best, based on surviving lines, commit history and recent activity.", refs, ["facts:knowledge"])
    when = card("Who committed and when", calendar_html(g, names, pal, g.get("tags") or []), "facts-calendar", None, refs, ["facts:git"])
    return main + when + know


# --------------------------------------------------------------------------- tracker pages


def is_open(g):
    return not g.get("res") or g["res"]["action"] == "wrong"


def collect_gaps(reports):
    """Every open item, plus the ones the user has since confirmed or answered (they carry 'res')."""
    rows, order = [], [r for r, _, _ in REPORTS]
    for rid in order:
        rep = reports.get(rid)
        if not rep:
            continue
        for c in claims_of(rid, rep):
            node = c["node"]
            conf = node.get("was") or c["conf"]
            if conf in ("inferred", "unknown"):
                rows.append({"kind": "inference" if conf == "inferred" else "unknown", "report": rid, "statement": c["text"],
                             "confirm": c["note"] or "", "cites": c["cites"], "node": node, "id": node.get("gid"), "res": node.get("user")})
    for it in (reports.get("gaps") or {}).get("items", []):
        rows.append({"kind": it["kind"], "report": it.get("report") or "gaps", "statement": it["statement"],
                     "confirm": it.get("how_to_confirm", ""), "cites": list(it.get("cite") or []) + inline_cites(it["statement"]),
                     "node": it, "id": it.get("gid"), "res": it.get("user")})
    rank = {k: i for i, k in enumerate(GAP_KINDS)}
    rows.sort(key=lambda r: (not is_open(r), rank[r["kind"]], order.index(r["report"]) if r["report"] in order else 99))
    return rows


def decision_cell(g):
    u = g.get("res")
    if not u:
        return '<span class="muted">Open</span>'
    label = {"confirm": "Confirmed by you", "answer": "Answered by you", "wrong": "Disputed by you"}[u["action"]]
    variant = "destructive" if u["action"] == "wrong" else "secondary"
    cls = "basis-unknown" if u["action"] == "wrong" else "basis-confirmed"
    return badge(label, cls, variant) + f'<div class="muted">{E(str(u.get("date", ""))[:10])}{(": " + E(u["text"])) if u.get("text") else ""}</div>'


def panel_gaps(gaps, refs):
    live = [g for g in gaps if is_open(g)]
    counts = {k: sum(1 for g in live if g["kind"] == k) for k in GAP_KINDS}
    done = len(gaps) - len(live)
    tone = lambda n, sev="": f"{sev}{'' if n else ' zero'}".strip()
    cards = stats_html([("Unknowns", counts["unknown"], "could not be found or inferred", tone(counts["unknown"], "sev-destructive")),
                        ("Inferences", counts["inference"], "reasoned from context, not stated", tone(counts["inference"], "sev-primary")),
                        ("Assumptions", counts["assumption"], "taken as true to proceed", tone(counts["assumption"], "sev-secondary")),
                        ("Resolved by you", done, "confirmed or answered", tone(done)), ("Coverage notes", counts["coverage"], "what was and was not read", tone(counts["coverage"]))])
    rows = [[f'<code class="gid">{E(g.get("id") or "")}</code>', gap_badge(g["kind"]), f'<a href="#{g["report"]}">{E(TITLES.get(g["report"], g["report"]))}</a>', inline(g["statement"], refs),
             decision_cell(g), inline(g["confirm"], refs) or '<span class="muted">not stated</span>', refs.mark(new_cites(g["cites"], g["statement"], g["confirm"]))] for g in gaps]
    hint = '<p class="muted">To confirm an item or give the answer to an unknown, ask Claude to run <code>/dossier confirm</code> with the ID. Your decisions are kept across rebuilds.</p>'
    return cards + card("Tracker", hint + (render_table(["ID", "Type", "Report", "Statement", "Status", "What would confirm it", "Evidence"], rows, refs, "t-gaps", True, True) if rows else '<p>Nothing is outstanding.</p>'), "tracker", kind="llm")


def panel_corrections(state, refs, present=frozenset()):
    rows = []
    for c in reversed(state.get("corrections", [])):
        rows.append([E(c["id"]), E(c["date"][:10]), f'<a href="#{c["report"]}">{E(TITLES.get(c["report"], c["report"]))}</a>' if c["report"] in TITLES else E(c["report"]),
                     inline(c.get("said", ""), refs) or '<span class="muted">not recorded</span>', inline(c["correction"], refs), E(c.get("status", "pending")), f'<code>{E(str(c.get("sha", ""))[:10])}</code>'])
    body = render_table(["ID", "Date", "Report", "What the dossier said", "Correction from the user", "Status", "Commit when recorded"], rows, refs, "t-corr", True, True) if rows else \
        '<p>No corrections have been recorded yet. If something in this dossier is wrong, tell Claude and it will be recorded here and applied on the next build.</p>'
    types = state.get("contributor_types", {})
    if types:
        body += "<h3>Contributor type overrides</h3>" + render_table(["Identity", "Set to"], [[E(k), E(v)] for k, v in types.items()], refs, "t-ovr", False, True)
    out = card("Tracker", body, "corrections-list")
    res = state.get("resolutions", {})
    if res:
        label = {"confirm": "Confirmed", "answer": "Answered", "wrong": "Disputed"}
        tr = {t["id"]: t for t in state.get("tracked", [])}
        rrows = [[f'<code class="gid">{E(i)}</code>', E(str(r.get("date", ""))[:10]), f'<a href="#{r["report"]}">{E(TITLES.get(r["report"], r["report"]))}</a>' if r.get("report") in TITLES else E(r.get("report", "")),
                  E(r.get("statement") or tr.get(i, {}).get("statement", "")), label[r["action"]], E(r.get("text") or "") or '<span class="muted">no note</span>',
                  "Applied to a statement in this build" if i in present else "No matching statement in this build. Kept, and applied if it returns."]
                 for i, r in sorted(res.items())]
        out += card("Your confirmations and answers", render_table(["ID", "Date", "Report", "Statement", "Decision", "Your note", "State"], rrows, refs, "t-res", True, True),
                    "resolutions-list", "Decisions about inferences, unknowns and assumptions. They are stored with the dossier and applied on every build.")
    return out


def panel_history(entries, refs):
    def num(n): return f'<span class="num">{n}</span>'
    rows = [[f'<span class="nw">{E(h["date"][:10])}</span><div class="muted">{E(h["date"][11:16])} UTC</div>', f'<span class="nw"><code>{E(h["short"])}</code>{refs.mark(["commit:" + h["sha"]])}</span>', E(h.get("branch") or h.get("ref") or ""),
             E(h["summary"]) + (f'<div class="muted">{E(h["note"])}</div>' if h.get("note") else ""),
             num(h["gaps"]["unknown"]), num(h["gaps"]["inference"]), num(h["gaps"]["assumption"]), f'<span class="nw">{E(h["skill_version"])}</span>'] for h in reversed(entries)]
    return card("Dossier changelog", render_table(["Built", "Commit", "Branch", "What changed", "Unknown", "Inferred", "Assumed", "Skill version"], rows, refs, "t-hist", False, True,
                group=[("", 4), ("Open items at that build", 3), ("", 1)]), "history", "Open items are the unknowns, inferences and assumptions listed in the gaps report at the time of each build.")


def panel_risk_counts(rep):
    counts = {s: 0 for s in SEVERITIES}
    for b in rep.get("blocks", []):
        if b.get("type") == "table" and "Severity" in b.get("columns", []):
            i = b["columns"].index("Severity")
            for r in b.get("rows", []):
                v = str(r["cells"][i]).strip().lower()
                if v in counts:
                    counts[v] += 1
    inferred = sum(1 for c in claims_of("risks", rep) if c["conf"] == "inferred")
    tiles = [(Raw(sev_badge(s.capitalize())), counts[s], "", f"sev-{SEV_TONE[s]}" + ("" if counts[s] else " zero")) for s in SEVERITIES[:4]]
    return stats_html(tiles + [("Based on inference", inferred, "risks without direct evidence")])


# --------------------------------------------------------------------------- page assembly

PANELS_AFTER = {
    "delivery": lambda f, r, ctx: panel_env(f, r) + panel_secrets(f, r),
}


def count_pill(n, kind):
    return f'<span class="count c-{kind}{" zero" if not n else ""}">{n}</span>'


def part_title(title, blurb):
    return f'<div class="part"><h2>{E(title)}</h2><p>{E(blurb)}</p></div>'


def panel_dossier(facts, reports, state, ctx, refs):
    allc = [c for rid, _, a in REPORTS if a for c in claims_of(rid, reports.get(rid) or {})]
    n = {k: sum(1 for c in allc if c["conf"] == k) for k in CONF}
    total = len(allc) or 1
    st = ctx["cites"].status
    c = facts["chunks"]
    skipped = sum(facts["files"]["excluded"].values())
    chunks = f"{fmt(c['chunk_count'])} chunk{'' if c['chunk_count'] == 1 else 's'}"
    tiles = stats_html([("Statements", fmt(len(allc)), f"across {sum(1 for x in REPORTS if x[2])} reports"),
                        ("Confirmed", fmt(n["confirmed"]), f"{100 * n['confirmed'] / total:.0f}% stated in the code"),
                        ("Inferred", fmt(n["inferred"]), f"{100 * n['inferred'] / total:.0f}% reasoned from context"),
                        ("Unknown", fmt(n["unknown"]), f"{100 * n['unknown'] / total:.0f}% not found"),
                        ("Citations", fmt(len(st)), f"{sum(1 for v in st.values() if not v['ok'])} unresolved"),
                        ("Files analyzed / not counted", f"{fmt(c['files'])} / {fmt(skipped)}", "excluded by the gatherer: generated, vendored, lock and binary files" if skipped else "nothing was left out"),
                        ("Reading mode / chunks", f"{c['mode'].capitalize()} / {fmt(c['chunk_count'])}", "read in one pass" if c["mode"] == "single" else f"each holds up to {fmt(c['budget'])} tokens"),
                        ("Size", f"~{compact(c['total_tokens'])} tokens", "file bytes divided by 3.5")])
    this = fact_box("Build", [("Built", E(ctx["built"])), ("Skill version", "dossier " + E(ctx["version"]))])
    return card("About this dossier", tiles + f'<div class="facts-groups one">{this}</div>', "dossier-build",
                "Everything is pinned to one commit, so every citation stays valid.", refs, "facts:chunks")


def flags_html(rid, reports, state, ctx=None):
    ok = '<span class="flags"><span class="flag ok" title="Nothing open: no inferences or unknowns"></span></span>'
    if rid == "dossier":
        bad = sum(1 for v in ctx["cites"].status.values() if not v["ok"]) if ctx else 0
        return ok if not bad else f'<span class="flags"><span class="flag unk" title="{bad} unresolved citation(s)">{bad}</span></span>'
    if rid == "corrections":
        n = sum(1 for c in state.get("corrections", []) if c.get("status") != "applied")
        return f'<span class="flags"><span class="flag pend" title="{n} correction(s) not yet applied">{n}</span></span>' if n else ok
    if not reports.get(rid):
        return '<span class="flags"><span class="flag none" title="Not written yet"></span></span>'
    cl = claims_of(rid, reports.get(rid) or {})
    inf, unk = sum(1 for c in cl if c["conf"] == "inferred"), sum(1 for c in cl if c["conf"] == "unknown")
    out = (f'<span class="flag inf" title="{inf} inferred statement(s)">{inf}</span>' if inf else "") + (f'<span class="flag unk" title="{unk} unknown">{unk}</span>' if unk else "")
    return f'<span class="flags">{out}</span>' if out else ok


CARD_HEAD = re.compile(r'<div class="card (panel|block)([^"]*)"( id="[^"]*")?><header><h([23])>(.*?)</h\4>')


def with_contents(rid, body):
    """Give every named card an anchor and return (body, contents card) listing the cards in page order."""
    entries = []

    def sub(m):
        kind, extra, idattr, lvl, inner = m.groups()
        cid = idattr[5:-1] if idattr else f"{rid}-c{len(entries) + 1}"
        entries.append((cid, re.sub(r"\s*<sup.*$", "", inner).strip()))
        return f'<div class="card {kind}{extra}" id="{cid}"><header><h{lvl}>{inner}</h{lvl}>'
    body = CARD_HEAD.sub(sub, body)
    entries.append((f"{rid}-refs", "References"))
    items = "".join(f'<li><a href="#{cid}">{title}</a></li>' for cid, title in entries)
    return body, f'<div class="card toc-card" id="{rid}-toc"><header><h2>Contents</h2></header><section><ol class="toc">{items}</ol></section></div>'


def build_page(rid, reports, facts, state, ctx):
    refs = Refs(rid, ctx["cites"])
    title = TITLES[rid]
    rep = reports.get(rid) or {}
    parts, pre = [], ""
    if rid == "dossier":
        headline = "How this dossier was built, how complete it is, and what changed since the last build."
        allc = [c for r_, _, a_ in REPORTS if a_ for c in claims_of(r_, reports.get(r_) or {})]
        n = {k: sum(1 for c in allc if c["conf"] == k) for k in CONF}
        summary_html = (f"<p>This dossier describes {E(facts['repo']['name'])} at one pinned commit, so every citation points at the same code. "
                        f"It holds {fmt(len(allc))} statements: {n['confirmed']} confirmed in the code or history, {n['inferred']} inferred from context and {n['unknown']} for which nothing was found.</p>"
                        f"<p>Built {E(ctx['built'])} with dossier {E(ctx['version'])}. {len(ctx['history'])} build{'' if len(ctx['history']) == 1 else 's'} recorded so far.</p>")
        parts.append(panel_dossier(facts, reports, state, ctx, refs))
        idx, tot = [], {k: 0 for k in CONF}
        for r, t, authored in REPORTS[1:]:
            rr = reports.get(r) or {}
            cl = claims_of(r, rr) if authored else []
            cnt = {k: sum(1 for c in cl if c["conf"] == k) for k in CONF}
            for k in CONF:
                tot[k] += cnt[k]
            idx.append([f'<a href="#{r}">{E(t)}</a>', E(rr.get("headline", "") if authored else "Corrections the user has given, with status."),
                        *([count_pill(cnt[k], k) for k in CONF] if authored else ['<span class="muted">n/a</span>'] * 3)])
        parts.append(card("Reports in this dossier", render_table(["Report", "In one sentence", "Confirmed", "Inferred", "Unknown"], idx, refs, "t-index", False, True,
                     group=[("", 2), ("Statements by basis", 3)],
                     foot=["<strong>Total</strong>", f'<span class="muted">{sum(tot.values())} statements in all</span>', *[count_pill(tot[k], k) for k in CONF]]), "report-index",
                     "Each count is a number of statements. Confirmed ones are stated in the code or history, inferred ones are reasoned from context, and unknown ones were not found.", kind="llm"))
        parts.append(panel_history(ctx["history"], refs))
    elif rid == "corrections":
        headline = "Everything the user has corrected, and whether the correction has been applied."
        summary_html = "<p>Corrections from the user always win over what the gatherer or Claude inferred. They are applied on every later build.</p>"
        parts.append(panel_corrections(state, refs, {g["id"] for g in ctx["gaps"] if g.get("id")}))
    else:
        headline = rep.get("headline", "This report has not been written yet.")
        summary_html = md(rep.get("summary", ""), refs) or '<p class="muted">Not generated.</p>'
        if rid == "overview":
            parts.append(panel_git(facts, refs, ctx))
            parts.append(panel_dependencies(facts, refs))
        if rid == "risks" and rep:
            parts.append(panel_risk_counts(rep))
        if rid == "contributors":
            parts.append(panel_contributors(facts, refs))
        blocks = render_blocks(rep.get("blocks", []), refs, rid)
        if blocks:
            parts.append(f'<div class="findings">{blocks}</div>')
        if rid == "gaps":
            parts.append(panel_gaps(ctx["gaps"], refs))
        if rid in PANELS_AFTER:
            parts.append(PANELS_AFTER[rid](facts, refs, ctx))
    body, toc = with_contents(rid, "".join(parts))
    top = "" if rid in BARE_REPORTS else f'<div class="card summary llm"><header><h2>Executive summary</h2></header><section>{summary_html}</section></div>' + toc
    return (f'<section class="report" id="{rid}" hidden><header class="report-head"><h1>{E(title)}</h1><p class="headline">{inline(headline, refs)}</p>{SHADE_KEY}</header>{pre}'
            + top + body + f'<div class="card refs-card" id="{rid}-refs"><header><h2>References</h2><p>Links open the source at the pinned commit.</p></header><section>{refs.listing()}</section></div></section>')


NAV_GROUPS = [("Orientation", ["dossier", "overview", "capabilities", "interfaces"]), ("Design", ["architecture", "domain-logic", "data", "code-tour"]),
              ("Operations and people", ["failures", "delivery", "contributors"]), ("Tracking", ["risks", "gaps", "corrections"])]


PLACEHOLDER = re.compile(r"\{\{|\}\}|\$\{|<%|%>|\[\[|<[A-Za-z_ -]+>$|^(your|my)[ _-]")


def real(v):
    """A manifest value that is set and is not a template placeholder such as {{project_name}}."""
    v = (v or "").strip()
    return v if v and not PLACEHOLDER.search(v) else ""


def open_pills(reports):
    """Two pills for the title bar: how many statements in the dossier are inferred, and how many are unknown."""
    allc = [c for rid, _, authored in REPORTS if authored for c in claims_of(rid, reports.get(rid) or {})]
    out = ""
    for conf, noun in (("inferred", "inference"), ("unknown", "unknown")):
        n = sum(1 for c in allc if c["conf"] == conf)
        word = noun + ("" if n == 1 or noun == "unknown" else "s")
        out += f'<a class="count pill c-{conf}" href="#gaps" data-tip="{n} {conf} statement{"" if n == 1 else "s"} in this dossier. Open the tracker.">{n} {word}</a>'
    return out


def main_manifest(facts):
    """The manifest that names the project: the named one nearest the root, or {}."""
    ms = [m for m in facts["manifests"] if real(m.get("name")) and m["name"] != m["path"].rsplit("/", 1)[-1]]
    ms.sort(key=lambda m: m["path"].count("/"))
    return ms[0] if ms else {}


def masthead(facts, reports):
    r = facts["repo"]
    m = main_manifest(facts)
    name = real(m.get("name")) or r["name"]
    desc = real(m.get("description")) or real((facts.get("readme") or {}).get("excerpt"))
    remote = gather.remote_info((r["remote"] or {}).get("url"))
    link = remote.get("web_base") or remote.get("url") or "no remote configured"
    return {"name": name, "description": desc, "ref": r["branch"] or r["ref"], "short": r["short"], "sha": r["sha"],
            "remote": link, "date": r["commit_date"]}


def render_html(facts, reports, state, history, version, cites):
    gaps = collect_gaps(reports)
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ctx = {"cites": cites, "gaps": gaps, "history": history, "built": built, "version": version}
    mh = masthead(facts, reports)
    build = lambda: "".join(build_page(rid, reports, facts, state, ctx) for rid, _, _ in REPORTS)
    pages = build()
    dropped, stale = cites.plan_view()      # the first pass recorded which files and ranges are cited
    if stale:
        pages = build()
    if dropped:
        print(f"warning: {len(dropped)} cited file(s) are not embedded in the code viewer, to keep the page small: {', '.join(dropped[:5])}{' ...' if len(dropped) > 5 else ''}")
    files = {p: {"lines": cites.source(p)[0]} for p in cites.windows}
    windows = dict(cites.windows)
    for which, path in (("gather", GATHERER_PATH), ("deps", DEPS_PATH)):      # the gatherer's own code, so a "measured facts" citation can show how its numbers were measured
        src = gatherer_source(which)
        files[path], windows[path] = {"lines": src}, viewer.pick_window(src, [gatherer_range(k) for k in FACT_INFO if gatherer_path(k) == path])
    jsn = lambda d: json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/").replace("<!--", "<\\u0021--")
    numbered = {rid: i for i, (rid, _, _) in enumerate(REPORTS, 1)}
    groups = "".join(
        f'<div role="group" aria-labelledby="nav-g{gi}"><h3 id="nav-g{gi}">{E(label)}</h3><ul>'
        + "".join(f'<li><a href="#{rid}" data-nav="{rid}"><span class="n">{numbered[rid]:02d}</span><span class="t">{E(TITLES[rid])}</span>{flags_html(rid, reports, state, ctx)}</a></li>' for rid in ids)
        + "</ul></div>" for gi, (label, ids) in enumerate(NAV_GROUPS))
    rail = "".join(f'<a href="#{rid}" data-nav="{rid}" title="{numbered[rid]}. {E(TITLES[rid])}" aria-label="{E(TITLES[rid])}">{numbered[rid]}</a>' for rid, _, _ in REPORTS)
    remote_short = re.sub(r"^https?://", "", mh["remote"]).removesuffix(".git")
    source = (f'<a class="side-source" href="{E(mh["remote"])}" target="_blank" rel="noopener">{E(remote_short)}</a>' if mh["remote"].startswith("http")
              else f'<span class="side-source">{E(remote_short)}</span>')
    head = (f'<header class="masthead"><div class="masthead-inner"><div class="mh-row">'
            f'<button class="btn" data-variant="outline" data-size="sm" id="menu-toggle" type="button">Menu</button>'
            f'<h1>{E(mh["name"])}</h1>{source}'
            f'<span class="chips">{badge(mh["ref"], "", "secondary")}{badge("commit " + mh["short"], "", "outline")}{badge(mh["date"], "", "outline")}{open_pills(reports)}</span>'
            '</div>'
            f'<div class="mh-row2"><p class="lede" title="{E(mh["description"])}">{E(mh["description"][:300])}</p></div></div>'
            '</header>')
    css = (VENDOR / "basecoat.min.css").read_text() + "\n" + (ASSETS / "dossier.css").read_text()
    mermaid = (VENDOR / "mermaid.min.js").read_text().replace("</script", "<\\/script").replace("<!--", "<\\!--")
    out = (ASSETS / "template.html").read_text()
    for k, v in {"TITLE": E(f"{mh['name']} dossier"), "CSS": css, "NAV": groups, "RAIL": rail, "MASTHEAD": head, "REPORTS": pages, "MERMAID": mermaid,
                 "BASECOAT_JS": (VENDOR / "basecoat.min.js").read_text(), "JS": (ASSETS / "dossier.js").read_text(),
                 "NAME": E(mh["name"]), "SHORT": E(mh["short"]), "CODE": viewer.embed(files, windows),
                 "CAL": jsn(calendar_data(facts)), "FACTS": jsn({k: {"t": v[0], "x": v[1]} for k, v in FACT_INFO.items()})}.items():
        out = out.replace(f"<!--@{k}-->", v)
    return out, gaps
