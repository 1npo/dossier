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
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import gather
from gather import Repo

ROOT = Path(__file__).resolve().parent.parent
ASSETS, VENDOR = ROOT / "assets", ROOT / "vendor"

REPORTS = [  # id, title, written by Claude?
    ("dossier", "This dossier", False), ("overview", "Overview", True), ("capabilities", "Capabilities", True),
    ("interfaces", "Interfaces", True), ("architecture", "Architecture", True), ("domain-logic", "Domain logic", True),
    ("data", "Data model", True), ("code-tour", "Code tour", True),
    ("failures", "Failure modes", True), ("delivery", "Delivery, config and secrets", True),
    ("risks", "Risk register", True), ("contributors", "Contributors", True),
    ("gaps", "Gaps and assumptions", True), ("corrections", "Corrections", False),
]
TITLES = {r: t for r, t, _ in REPORTS}
CONF = ("confirmed", "inferred", "unknown")
BLOCKS = ("text", "table", "diagram", "list")
GAP_KINDS = ("assumption", "unknown", "inference", "coverage")
SEVERITIES = ("critical", "high", "medium", "low", "info")
RISK_COLUMNS = ("ID", "Risk", "Category", "Severity")
FACT_KEYS = {k: f"facts-{k}" for k in ("git", "languages", "hot_files", "manifests", "env_vars",
                                       "secret_signals", "contributors", "ownership", "areas", "chunks")}
FACT_KEYS["inventory"] = "facts-git"  # retired file-name inventory; old reports may still cite it
OPTIONAL_REPORTS = ("domain-logic",)  # reports added after v0.1: a dossier built before them still renders
DIAGRAM_START = re.compile(r"^\s*(%%\{.*?\}%%\s*)?(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram(-v2)?|erDiagram|journey|gantt|pie|mindmap|timeline|gitGraph|quadrantChart|requirementDiagram|C4\w+|sankey-beta|xychart-beta|block-beta|architecture-beta)\b", re.S)
INLINE_CITE = re.compile(r"\[\[(.+?)\]\]")
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

# --------------------------------------------------------------------------- citations


def parse_cite(raw):
    raw = raw.strip()
    if raw.startswith("commit:"):
        sha = raw[7:].strip().lower()
        return {"kind": "commit", "sha": sha, "key": f"commit:{sha}", "text": f"commit {sha[:10]}"}
    if raw.startswith("facts:"):
        k = raw[6:].strip()
        return {"kind": "facts", "name": k, "key": f"facts:{k}", "text": f"profiler facts: {k}"}
    m = re.match(r"^(.+?)(?::(\d+)(?:-(\d+))?)?$", re.sub(r"^(\./|/)+", "", raw))
    path, a, b = m.group(1), m.group(2), m.group(3)
    a, b = (int(a) if a else None), (int(b) if b else (int(a) if a else None))
    key = path + (f":{a}-{b}" if a and b and b != a else f":{a}" if a else "")
    return {"kind": "file", "path": path, "a": a, "b": b, "key": key, "text": key}


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

    def mark(self, raws):
        out = []
        for raw in dict.fromkeys(raws):
            n = self.num(raw)
            tip = E(parse_cite(raw)["text"])
            out.append(f'<a href="#ref-{self.rid}-{n}" data-tip="{tip}" aria-label="Source {n}: {tip}">[{n}]</a>')
        return f'<sup class="cite">{"".join(out)}</sup>' if out else ""

    def listing(self):
        if not self.keys:
            return '<p class="muted">This report cites no sources.</p>'
        rows = []
        for i, k in enumerate(self.keys, 1):
            c = self.parsed[k]
            st = self.cites.check(c)
            url = self.cites.url(c)
            label = E(c["text"])
            if not st["ok"]:
                link = f'<span class="bad">{label}</span> <span class="muted">unresolved: {E(st["msg"])}</span>'
            elif url:
                ext = "" if c["kind"] == "facts" else ' target="_blank" rel="noopener noreferrer"'
                link = f'<a href="{E(url)}"{ext}>{label}</a>'
            else:
                link = f'<code>git show {E(c["sha"][:10])}</code>'
            kind = {"file": "file", "tree": "directory", "blob": "file", "commit": "commit", "facts": "measured by the profiler"}.get(st["type"], "")
            rows.append(f'<li id="ref-{self.rid}-{i}">{link} <span class="muted">· {kind}</span></li>')
        return "<ol class=\"refs\">" + "".join(rows) + "</ol>"


# --------------------------------------------------------------------------- text helpers


BARE_FILE = re.compile(r"(?<![\w/.\-])((?:[\w.\-]+/)*(?:[\w\-]+\.(?:sh|bash|zsh|py|js|mjs|ts|tsx|jsx|json|ya?ml|toml|ini|cfg|conf|md|go|rs|rb|java|kt|c|h|cpp|hpp|cs|php|sql|tf|html|css|txt|lock|mk|service|timer|socket|env|xml|gradle)|Makefile|Dockerfile|Justfile|Gemfile))(?![\w\-]|\.\w)")


def code_files(s):
    """Wrap bare file names in prose (install.sh, src/app.py) in <code>, leaving markup and existing code alone."""
    parts = re.split(r"(<code>.*?</code>|<[^>]+>)", s)
    return "".join(p if i % 2 else BARE_FILE.sub(r"<code>\1</code>", p) for i, p in enumerate(parts))


def inline(s, refs):
    s = html.escape(str(s or ""), quote=False)

    def cite_sub(m):
        return refs.mark([x.strip() for x in html.unescape(m.group(1)).split(", ") if x.strip()])
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
            found += [x.strip() for x in m.group(1).split(", ") if x.strip()]
    return found


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
        return f'<code class="gid" title="Use this ID with /dossier confirm">{E(node["gid"])}</code>'
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


def sev_badge(v):
    key = str(v).strip().lower()
    return badge(v, "", {"critical": "destructive", "high": "destructive", "medium": "primary", "low": "secondary"}.get(key, "outline"))


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
            if b.get("type") not in BLOCKS:
                errors.append(f"{tag}: 'type' must be one of {', '.join(BLOCKS)}.")
            elif b["type"] == "table":
                cols = b.get("columns")
                if not isinstance(cols, list) or not cols:
                    errors.append(f"{tag}: a table needs 'columns'.")
                    continue
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


def provenance(node, refs):
    conf = node.get("conf")
    note = node.get("note")
    note_html = f'<span class="muted"> {inline(note, refs)}</span>' if note and conf != "confirmed" else ""
    return f'<div class="prov">{basis_for(node)}{gid_tag(node)}{refs.mark(list(node.get("cite") or []))}{note_html}</div>{user_note(node.get("user"))}'


_NW = re.compile(r"\d{4}-\d{2}-\d{2}|[\w.]+(?:-[\w.]+)*\[bot\]|\b[A-Za-z]+-\d\w*")


def keep_whole(h):
    """Stop dates and bot names breaking at their hyphens (text outside tags only)."""
    return "".join(seg if seg.startswith("<") else _NW.sub(lambda m: f'<span class="nw">{m.group(0)}</span>', seg) for seg in re.split(r"(<[^>]*>)", h))


def cell_html(cell, refs):
    if refs.cites.path_like(cell):
        return f'<code>{E(str(cell).strip()).replace("/", "/<wbr>")}</code>'
    return keep_whole(inline(cell, refs))


def render_table(columns, rows, refs, tid, filterable=True, plain=False, group=None, foot=None):
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
            tds.append(f"<td>{sev_badge(cell)}</td>" if col.strip().lower() == "severity" else f"<td>{cell_html(cell, refs)}</td>")
        note = f'<div class="muted">{inline(r.get("note"), refs)}</div>' if r.get("note") and r.get("conf") != "confirmed" else ""
        cites_ = list(r.get("cite") or []) + inline_cites(*r["cells"])
        body.append("<tr>" + "".join(tds) + f'<td class="basis-cell">{basis_for(r)}{gid_tag(r)}{note}{user_note(r.get("user"))}</td><td>{refs.mark(cites_)}</td></tr>')
    flt = f'<input class="input tbl-filter" type="search" data-target="{tid}" placeholder="Filter rows" aria-label="Filter rows">' if filterable and len(rows) > 6 else ""
    top = ("<tr class=\"group-row\">" + "".join(f'<th colspan="{n}"{" class=\"grp\"" if lbl else ""}>{E(lbl)}</th>' for lbl, n in group) + "</tr>") if group else ""
    tf = f'<tfoot><tr class="total-row">{"".join(f"<td>{c}</td>" for c in foot)}</tr></tfoot>' if foot else ""
    return f'{flt}<div class="table-container"><table class="table" id="{tid}"><thead>{top}<tr>{head}</tr></thead><tbody>{"".join(body)}</tbody>{tf}</table></div>'


def block_card(head, body, prov, extra="", action=""):
    h = f"<header><h3>{E(head)}</h3>{action}</header>" if head or action else ""
    return f'<div class="card block {extra}">{h}<section>{body}</section><footer>{prov}</footer></div>'


def render_block(b, refs, rid, idx, notes=None):
    t = b["type"]
    prov = provenance(b, refs) if t in ("text", "diagram") else ""
    if t == "text":
        return block_card(b.get("heading"), md(b["text"], refs), prov)
    if t == "list":
        lis = "".join(f'<li>{inline(i["text"], refs)} {basis_for(i) if (i["conf"] != "confirmed" or i.get("user")) else ""}{gid_tag(i)}{refs.mark(list(i.get("cite") or []))}'
                      + (f'<div class="muted">{inline(i.get("note"), refs)}</div>' if i.get("note") and i["conf"] != "confirmed" else "") + user_note(i.get("user")) + "</li>"
                      for i in b["items"])
        return f'<div class="card block"><header><h3>{E(b.get("heading") or "")}</h3></header><section><ul class="claims">{lis}</ul></section></div>' if b.get("heading") else \
            f'<div class="card block"><section><ul class="claims">{lis}</ul></section></div>'
    if t == "table":
        cap = f'<p class="muted">{inline(b["caption"], refs)}</p>' if b.get("caption") else ""
        h = f'<header><h3>{E(b["heading"])}</h3></header>' if b.get("heading") else ""
        return f'<div class="card block">{h}<section>{cap}{render_table(b["columns"], b["rows"], refs, f"t-{rid}-{idx}")}</section></div>'
    src = b["mermaid"].strip()
    title = b.get("heading") or b.get("title") or "Diagram"
    sub_ = f'<p>{E(b["title"])}</p>' if b.get("heading") and b.get("title") else ""
    return (f'<div class="card block diagram"><header><h3>{E(title)}</h3>{sub_}<div class="card-action"><button class="btn" data-variant="ghost" data-size="sm" type="button" data-expand>Expand</button></div></header>'
            f'<section><div class="mermaid-host" data-src="{E(src)}"><pre class="muted">Diagram loads when this report is opened.</pre></div>'
            f'{notes[0] if notes else ""}<details><summary class="muted">Diagram source</summary><pre>{E(src)}</pre></details></section><footer>{prov}{notes[1] if notes else ""}</footer></div>')


NOTES_HEAD = re.compile(r"^\s*notes?\s+(on|for)\b", re.I)


def render_blocks(blocks, refs, rid):
    """Render report blocks. A text block headed "Notes on ..." right after a diagram goes inside that diagram's card."""
    out, i = [], 0
    while i < len(blocks):
        b, nxt = blocks[i], blocks[i + 1] if i + 1 < len(blocks) else None
        if b["type"] == "diagram" and nxt and nxt["type"] == "text" and NOTES_HEAD.match(nxt.get("heading") or ""):
            notes = (f'<div class="diagram-notes"><h4>{E(nxt["heading"])}</h4>{md(nxt["text"], refs)}</div>', provenance(nxt, refs))
            out.append(render_block(b, refs, rid, i, notes))
            i += 2
            continue
        out.append(render_block(b, refs, rid, i))
        i += 1
    return "".join(out)


# --------------------------------------------------------------------------- measured panels


def card(title, body, pid=None, desc=None, refs=None, cite=None):
    mark = refs.mark([cite]) if refs and cite else ""
    d = f"<p>{E(desc)}</p>" if desc else ""
    idattr = f' id="{pid}"' if pid else ""
    return f'<div class="card panel"{idattr}><header><h2>{E(title)} {mark}</h2>{d}</header><section>{body}</section></div>'


def path_cell(path, refs, line=None):
    ref = f"{path}:{line}" if line else path
    return f"<code>{E(ref).replace('/', '/<wbr>')}</code>{refs.mark([ref])}"


def stats_html(items):
    cols = 3 if len(items) == 6 else min(len(items), 5)
    return f'<div class="stats" style="grid-template-columns:repeat({cols},minmax(0,1fr))">' + "".join(
        f'<div class="stat"><div class="k">{E(k)}</div><div class="v">{E(v)}</div><div class="s">{E(s)}</div></div>' for k, v, s in items) + "</div>"


def stack(parts):
    total = sum(parts.values()) or 1
    return '<span class="stack">' + "".join(f'<i class="{k}" style="width:{100 * v / total:.1f}%" title="{k}: {v}"></i>' for k, v in parts.items() if v) + "</span>"


def panel_git(f, refs):
    g, fl = f["git"], f["files"]
    deps = [d for m in f["manifests"] for d in m["dependencies"]]
    c = g["contributors"]
    stats = stats_html([
        ("Commits", fmt(g["commits"]), f"{fmt(g['merges'])} merges"),
        ("Contributors", fmt(c["total"]), f"{c['human']} human · {c['agent']} agent · {c['bot']} bot"),
        ("Active span", f"{(g['age_days'] / 365.25):.1f} years", f"{g['first_commit']} to {g['last_commit']}"),
        ("Tracked files", fmt(fl["tracked"]), f"{fmt(fl['tests'])} contain tests"),
        ("Code lines", fmt(fl["total_code_lines"]), f"{len([l for l in f['languages'] if l['kind'] == 'code'])} programming languages"),
        ("Dependencies", fmt(len(deps)), f"{sum(1 for d in deps if not d['dev'])} runtime · {sum(1 for d in deps if d['dev'])} dev"),
    ])
    months, tags = g["monthly"], g["tags"]
    ys = sorted({int(k[:4]) for k in months})
    yrs = [str(y) for y in range(ys[0], ys[-1] + 1)][-16:] if ys else []
    peak = max((v for k, v in months.items() if k[:4] in yrs), default=1)
    tagged = {t["date"][:7] for t in tags}
    def cell(y, m):
        k = f"{y}-{m:02d}"; v = months.get(k, 0)
        lvl = 0 if not v else 1 + min(3, int(4 * (v - 1) / max(peak, 1)))
        rel = " rel" if k in tagged else ""
        return f'<span class="hm l{lvl}{rel}" title="{k}: {v} commit{"" if v == 1 else "s"}{", release tag" if rel else ""}">{v or ""}</span>'
    head = '<span></span>' + "".join(f'<span class="hh">{n}</span>' for n in "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()) + '<span class="hh">Total</span>'
    body = "".join(f'<span class="hy">{y}</span>' + "".join(cell(y, m) for m in range(1, 13)) + f'<span class="ht">{fmt(g["yearly"].get(y, 0))}</span>' for y in yrs)
    heat = (f'<div class="activity-main"><h3>Commits by month</h3><div class="heat">{head}{body}</div>'
            f'<div class="heat-key muted"><span class="kg">Fewer commits <span class="hm l0"></span><span class="hm l1"></span><span class="hm l2"></span><span class="hm l3"></span><span class="hm l4"></span> More commits</span><span class="kg"><span class="hm rel keyrel"></span> Month with a release tag</span></div></div>') if yrs else ""
    def gap(i):
        if i + 1 >= len(tags): return "·"
        d = (datetime.strptime(tags[i]["date"], "%Y-%m-%d") - datetime.strptime(tags[i + 1]["date"], "%Y-%m-%d")).days
        return f"{d} days"
    n = max(5, min(14, len(yrs) + 1))
    rel = ""
    if tags:
        rows = "".join(f'<tr><td><code>{E(t["name"])}</code></td><td>{E(t["date"])}</td><td class="muted">{gap(i)}</td></tr>' for i, t in enumerate(tags[:n]))
        rel = f'<div class="activity-side"><h3>Recent releases</h3><table class="table"><thead><tr><th>Tag</th><th>Date</th><th>Gap</th></tr></thead><tbody>{rows}</tbody></table></div>'
    chart = f'<div class="activity">{heat}{rel}</div>' if heat else ""
    notes = "".join(alert(E(w)) for w in f["repo"]["warnings"])
    tags = ""
    return card("Repository at a glance", notes + stats + chart + languages_block(f, refs), "facts-git", refs=refs, cite="facts:git")


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



def panel_hot(f, refs, pid="facts-hot_files"):
    rows = [[path_cell(h["path"], refs), fmt(h["commits"]), fmt(h["churn"]), E(h["last_changed"]), f'{E(h["top_contributor"])} ({h["top_share_pct"]}%)'] for h in f["hot_files"][:15]]
    return card("Most changed files", render_table(["File", "Commits", "Lines changed", "Last changed", "Main contributor"], rows, refs, "t-hot", False, True),
                pid, "Files that change often are where the work and the risk tend to concentrate.", refs, "facts:hot_files")


def panel_manifests(f, refs):
    if not f["manifests"]:
        return card("Project manifests", '<p class="muted">No package manifests were found. Name, version and dependencies are unknown.</p>', "facts-manifests", refs=refs, cite="facts:manifests")
    rows = []
    for m in f["manifests"]:
        runtime = sum(1 for d in m["dependencies"] if not d["dev"])
        rows.append([path_cell(m["path"], refs), E(m["ecosystem"]), E(real(m["name"]) or "unknown"), E(m["version"] or "unknown"),
                     f'{runtime} runtime · {m["dependency_count"] - runtime} dev', E(real(m["description"])[:120])])
    details = "".join(
        f'<details class="deps"><summary><code>{E(m["path"]).replace("/", "/<wbr>")}</code> <span class="muted">· {m["dependency_count"]} dependenc{"y" if m["dependency_count"] == 1 else "ies"}</span></summary><p>' + ", ".join(f'<code>{E(d["name"])}</code>{" (dev)" if d["dev"] else ""}' for d in m["dependencies"]) + "</p></details>"
        for m in f["manifests"] if m["dependencies"])
    return card("Project manifests", render_table(["Manifest", "Ecosystem", "Name", "Version", "Dependencies", "Description"], rows, refs, "t-man", False, True) + details,
                "facts-manifests", refs=refs, cite="facts:manifests")


def panel_chunks(f, refs):
    c = f["chunks"]
    adv = "".join(f"<li>{E(a)}</li>" for a in c["advice"])
    return card("Reading coverage", f'<p>{fmt(c["files"])} files, about {fmt(c["total_tokens"])} tokens. Reading mode: <strong>{E(c["mode"])}</strong>'
                f' ({c["chunk_count"]} chunk{"s" if c["chunk_count"] != 1 else ""} of up to {fmt(c["budget"])} tokens).</p><ul>{adv}</ul>'
                '<p class="muted">Every analyzable file was assigned to a chunk and none were skipped. Files that were not counted are listed under Repository at a glance.</p>',
                "facts-chunks", refs=refs, cite="facts:chunks")


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


def own_bar(parts, total, cls_of, label):
    """One stacked bar: parts are (id, name, lines); anyone without a colour is grouped under Others."""
    segs = []
    for cid, name, n in parts:
        if n and total:
            segs.append(f'<i class="{cls_of.get(cid, "own-other")}" style="width:{100 * n / total:.2f}%" title="{E(name)}: {fmt(n)} lines ({100 * n / total:.1f}%) {E(label)}"></i>')
    return '<span class="own-bar">' + "".join(segs) + "</span>"


def panel_ownership(f, refs):
    o = f.get("ownership")
    if not o:
        return card("Who wrote the code today", '<p class="muted">Code ownership was not measured in this profile. Run prepare again to measure it.</p>', "facts-ownership", refs=refs, cite="facts:ownership")
    ppl, total = o["people"], o["total_lines"]
    top = ppl[:6]
    cls_of = {p["id"]: f"lang-{i + 1}" for i, p in enumerate(top)}
    shown = sum(p["lines"] for p in top)
    parts = [(p["id"], p["name"], p["lines"]) for p in top] + [("", "Everyone else", total - shown)]
    legend = "".join(f'<li><b class="{cls_of[p["id"]]}"></b>{E(p["name"])} <span class="muted">{p["share_pct"]}%</span></li>' for p in top)
    if total - shown > 0:
        legend += f'<li><b class="own-other"></b>Everyone else <span class="muted">{100 * (total - shown) / total:.1f}%</span></li>'
    bt = o["by_type"]
    tiles = stats_html([("Lines attributed", fmt(total), f"{fmt(o['files_blamed'])} of {fmt(o['files_total'])} files"),
                        ("Contributors with code", fmt(len(ppl)) + ("+" if len(ppl) >= 30 else ""), "own at least one surviving line"),
                        ("Human", f"{100 * bt['human'] / total:.0f}%", f"{fmt(bt['human'])} lines"),
                        ("Agent", f"{100 * bt['agent'] / total:.0f}%", f"{fmt(bt['agent'])} lines"),
                        ("Bot", f"{100 * bt['bot'] / total:.0f}%", f"{fmt(bt['bot'])} lines")])
    rows = []
    for p in ppl[:20]:
        meter = f'<span class="meter"><i class="{cls_of.get(p["id"], "own-other")}" style="width:{max(p["share_pct"], 0.4):.1f}%"></i></span> {p["share_pct"]}%'
        where = ", ".join(f'<code>{E(a["area"])}</code> <span class="muted">{100 * a["lines"] / p["lines"]:.0f}%</span>' for a in p["top_areas"][:3])
        rows.append([f'<b class="own-dot {cls_of.get(p["id"], "own-other")}"></b>{E(p["name"])}', type_badge(p["type"]), fmt(p["lines"]), (meter, p["share_pct"]), where])
    table = render_table(["Contributor", "Type", "Lines", "Share of the codebase", "Where their code lives"], rows, refs, "t-own", False, True)
    arows = "".join(f'<div class="own-area"><code>{E(a["name"])}</code>{own_bar([(x["id"], x["name"], x["lines"]) for x in a["owners"]] + [("", "Others", a["lines"] - sum(x["lines"] for x in a["owners"]))], a["lines"], cls_of, "in " + a["name"])}'
                    f'<span class="muted">{fmt(a["lines"])} lines · {E(a["owners"][0]["name"])} {a["owners"][0]["share_pct"]:.0f}%</span></div>' for a in o["areas"][:12])
    body = (tiles + f'<h3>Share of all code lines</h3>{own_bar(parts, total, cls_of, "of the codebase")}<ul class="llegend">{legend}</ul>'
            + "<h3>By contributor</h3>" + table + "<h3>By area: who owns each part of the codebase</h3>" + f'<div class="own-areas">{arows}</div>'
            + f'<p class="muted">{E(o["note"])}</p>')
    return card("Who wrote the code today", body, "facts-ownership", "Share of the lines in the codebase at this commit that each contributor wrote, as opposed to how many commits they made.", refs, "facts:ownership")


def panel_contributors(f, refs):
    g, c = f["git"], f["git"]["contributors"]
    cb = g["commits_by_type"]
    total = sum(cb.values()) or 1
    cards = stats_html([(t.capitalize(), f"{c[t]} people", f"{fmt(cb[t])} commits ({100 * cb[t] / total:.0f}%)") for t in ("human", "agent", "bot")])
    assisted = ""
    if g["agent_assisted_commits"]:
        by = ", ".join(f"{k}: {v}" for k, v in g["agent_assisted_by"].items())
        assisted = f'<p>{fmt(g["agent_assisted_commits"])} commits carry an AI-assistant marker ({E(by)}). They are counted under "agent" in the area map below.</p>'
    rows = []
    for p in f["contributors"]["people"][:40]:
        areas = ", ".join(E(a["area"]) for a in p["top_areas"][:3])
        rows.append([E(p["name"]), type_badge(p["type"]), fmt(p["commits"]), f'{p["share_pct"]}%', f'{p["first"]} to {p["last"]}',
                     fmt(p["recent_commits_12m"]), f'+{fmt(p["added"])} / -{fmt(p["deleted"])}', fmt(p["assisted_commits"]), areas])
    more = f'<p class="muted">{f["contributors"]["not_listed"]} more contributors are in the profiler data but not shown. Table shows the top 40.</p>' if f["contributors"]["not_listed"] or len(f["contributors"]["people"]) > 40 else ""
    t1 = card("Contributors", cards + assisted + render_table(["Name", "Type", "Commits", "Share", "Active", "Last 12 months", "Lines +/-", "Agent-assisted", "Main areas"], rows, refs, "t-people", True, True)
              + more + f'<p class="muted">{E(f["contributors"]["classification_note"])}</p>', "facts-contributors", refs=refs, cite="facts:contributors")
    arows = []
    for a in f["areas"]:
        who = "<br>".join(f'{E(x["name"])} <span class="muted">({x["share_pct"]}%{", " + x["type"] if x["type"] != "human" else ""})</span>' for x in a["top"][:3])
        bt = {k: v["commits"] for k, v in a["by_type"].items()}
        state = "removed" if not a["exists"] else ("dormant" if not a["recent_commits_12m"] else "active")
        arows.append([f"<code>{E(a['name'])}</code>", state, fmt(a["files"]), fmt(a["commits"]), (stack(bt), bt.get("human", 0)), who, str(a["humans_for_80pct"]), E(a["last_active"])])
    t2 = card("Who knows which area", render_table(["Area", "State", "Files", "Commits", "Human / agent / bot", "Top contributors", "People for 80%", "Last active"], arows, refs, "t-areas", True, True)
              + '<p class="muted">"People for 80%" is how many human contributors account for 80% of the human commits in that area. A low number means knowledge is concentrated. '
                '"Removed" areas no longer exist at this commit but their history is kept.</p>', "facts-areas", "Large directories are split one or two levels deeper so the map stays useful.", refs, "facts:areas")
    return t1 + t2


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
    cards = stats_html([("Unknowns", counts["unknown"], "could not be found or inferred"), ("Inferences", counts["inference"], "reasoned from context, not stated"),
                        ("Assumptions", counts["assumption"], "taken as true to proceed"), ("Resolved by you", done, "confirmed or answered"), ("Coverage notes", counts["coverage"], "what was and was not read")])
    rows = [[f'<code class="gid">{E(g.get("id") or "")}</code>', gap_badge(g["kind"]), f'<a href="#{g["report"]}">{E(TITLES.get(g["report"], g["report"]))}</a>', inline(g["statement"], refs),
             decision_cell(g), inline(g["confirm"], refs) or '<span class="muted">not stated</span>', refs.mark(g["cites"])] for g in gaps]
    hint = '<p class="muted">To confirm an item or give the answer to an unknown, ask Claude to run <code>/dossier confirm</code> with the ID. Your decisions are kept across rebuilds.</p>'
    return card("Tracker", cards + hint + (render_table(["ID", "Type", "Report", "Statement", "Status", "What would confirm it", "Evidence"], rows, refs, "t-gaps", True, True) if rows else '<p>Nothing is outstanding.</p>'), "tracker")


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
    out = card("Recorded corrections", body, "corrections-list")
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
    return card("History of updates", render_table(["Built", "Commit", "Branch", "What changed", "Unknown", "Inferred", "Assumed", "Skill version"], rows, refs, "t-hist", False, True,
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
    return stats_html([(s.capitalize(), counts[s], "") for s in SEVERITIES[:4]] + [("Based on inference", inferred, "risks without direct evidence")])


# --------------------------------------------------------------------------- page assembly

PANELS_AFTER = {
    "overview": lambda f, r, ctx: panel_hot(f, r) + panel_manifests(f, r),
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
    r = facts["repo"]
    tiles = stats_html([("Statements", fmt(len(allc)), f"across {sum(1 for x in REPORTS if x[2])} reports"),
                        ("Confirmed", fmt(n["confirmed"]), f"{100 * n['confirmed'] / total:.0f}% stated in the code"),
                        ("Inferred", fmt(n["inferred"]), f"{100 * n['inferred'] / total:.0f}% reasoned from context"),
                        ("Unknown", fmt(n["unknown"]), f"{100 * n['unknown'] / total:.0f}% not found"),
                        ("Citations", fmt(len(st)), f"{sum(1 for v in st.values() if not v['ok'])} unresolved")])
    link = ctx["cites"].url({"kind": "commit", "sha": r["sha"]})
    sha = f'<a href="{E(link)}" target="_blank" rel="noopener noreferrer">{E(r["sha"])}</a>' if link else E(r["sha"])
    proj = ('<div class="facts-group project"><h3>The project <span class="muted">pinned for every citation</span></h3><dl class="facts"><dt>Pinned commit</dt><dd>' + sha + refs.mark(["commit:" + r["sha"]])
            + '</dd><dt>Branch or ref</dt><dd>' + E(r["branch"] or r["ref"]) + '</dd><dt>Commit date</dt><dd>' + E(r["commit_date"]) + "</dd></dl></div>")
    this = ('<div class="facts-group build"><h3>This dossier</h3><dl class="facts"><dt>Built</dt><dd>' + E(ctx["built"]) + '</dd><dt>Skill version</dt><dd>dossier ' + E(ctx["version"]) + "</dd></dl></div>")
    dl = f'<div class="facts-groups">{proj}{this}</div>'
    return card("About this build", tiles + dl, "dossier-build", "Everything is pinned to one commit, so every citation stays valid.")


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
                     "Each count is a number of statements. Confirmed ones are stated in the code or history, inferred ones are reasoned from context, and unknown ones were not found."))
        parts.append(panel_chunks(facts, refs))
        parts.append(panel_history(ctx["history"], refs))
    elif rid == "corrections":
        headline = "Everything the user has corrected, and whether the correction has been applied."
        summary_html = "<p>Corrections from the user always win over what the profiler or Claude inferred. They are applied on every later build.</p>"
        parts.append(panel_corrections(state, refs, {g["id"] for g in ctx["gaps"] if g.get("id")}))
    else:
        headline = rep.get("headline", "This report has not been written yet.")
        summary_html = md(rep.get("summary", ""), refs) or '<p class="muted">Not generated.</p>'
        if rid == "overview":
            parts.append(panel_git(facts, refs))
        if rid == "risks" and rep:
            parts.append(panel_risk_counts(rep))
        if rid == "contributors":
            parts.append(panel_ownership(facts, refs) + panel_contributors(facts, refs))
        blocks = render_blocks(rep.get("blocks", []), refs, rid)
        if blocks:
            parts.append(f'<div class="findings">{blocks}</div>')
        if rid == "gaps":
            parts.append(panel_gaps(ctx["gaps"], refs))
        if rid in PANELS_AFTER:
            parts.append(PANELS_AFTER[rid](facts, refs, ctx))
    return (f'<section class="report" id="{rid}" hidden><header class="report-head"><h1>{E(title)}</h1><p class="headline">{inline(headline, refs)}</p></header>{pre}'
            f'<div class="card summary"><header><h2>Executive summary</h2></header><section>{summary_html}</section></div>'
            + "".join(parts) + f'<div class="card refs-card"><header><h2>References</h2><p>Links open the source at the pinned commit.</p></header><section>{refs.listing()}</section></div></section>')


NAV_GROUPS = [("Orientation", ["dossier", "overview", "capabilities", "interfaces"]), ("Design", ["architecture", "domain-logic", "data", "code-tour"]),
              ("Operations and risk", ["failures", "delivery", "risks", "contributors"]), ("Tracking", ["gaps", "corrections"])]


PLACEHOLDER = re.compile(r"\{\{|\}\}|\$\{|<%|%>|\[\[|<[A-Za-z_ -]+>$|^(your|my)[ _-]")


def real(v):
    """A manifest value that is set and is not a template placeholder such as {{project_name}}."""
    v = (v or "").strip()
    return v if v and not PLACEHOLDER.search(v) else ""


def masthead(facts, reports):
    r = facts["repo"]
    ms = [m for m in facts["manifests"] if real(m.get("name")) and m["name"] != m["path"].rsplit("/", 1)[-1]]
    ms.sort(key=lambda m: m["path"].count("/"))  # prefer the manifest nearest the root
    m = ms[0] if ms else {}
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
    pages = "".join(build_page(rid, reports, facts, state, ctx) for rid, _, _ in REPORTS)
    numbered = {rid: i for i, (rid, _, _) in enumerate(REPORTS, 1)}
    groups = "".join(
        f'<div role="group" aria-labelledby="nav-g{gi}"><h3 id="nav-g{gi}">{E(label)}</h3><ul>'
        + "".join(f'<li><a href="#{rid}" data-nav="{rid}"><span class="n">{numbered[rid]:02d}</span><span class="t">{E(TITLES[rid])}</span>{flags_html(rid, reports, state, ctx)}</a></li>' for rid in ids)
        + "</ul></div>" for gi, (label, ids) in enumerate(NAV_GROUPS))
    remote_short = re.sub(r"^https?://", "", mh["remote"]).removesuffix(".git")
    source = (f'<a class="side-source" href="{E(mh["remote"])}" target="_blank" rel="noopener">{E(remote_short)}</a>' if mh["remote"].startswith("http")
              else f'<span class="side-source">{E(remote_short)}</span>')
    head = (f'<header class="masthead"><div class="masthead-inner"><div class="mh-row">'
            f'<button class="btn" data-variant="outline" data-size="sm" id="menu-toggle" type="button">Menu</button>'
            f'<h1>{E(mh["name"])}</h1>{source}'
            f'<span class="chips">{badge(mh["ref"], "", "secondary")}{badge("commit " + mh["short"], "", "outline")}{badge(mh["date"], "", "outline")}</span>'
            '</div>'
            f'<div class="mh-row2"><p class="lede" title="{E(mh["description"])}">{E(mh["description"][:300])}</p></div></div>'
            '</header>')
    css = (VENDOR / "basecoat.min.css").read_text() + "\n" + (ASSETS / "dossier.css").read_text()
    mermaid = (VENDOR / "mermaid.min.js").read_text().replace("</script", "<\\/script").replace("<!--", "<\\!--")
    out = (ASSETS / "template.html").read_text()
    for k, v in {"TITLE": E(f"{mh['name']} dossier"), "CSS": css, "NAV": groups, "MASTHEAD": head, "REPORTS": pages, "MERMAID": mermaid,
                 "BASECOAT_JS": (VENDOR / "basecoat.min.js").read_text(), "JS": (ASSETS / "dossier.js").read_text(),
                 "NAME": E(mh["name"]), "SHORT": E(mh["short"])}.items():
        out = out.replace(f"<!--@{k}-->", v)
    return out, gaps
