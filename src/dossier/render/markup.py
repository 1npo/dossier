"""The page's HTML primitives: escaping, inline citations and Markdown, badges, tables and stat tiles.

The measured cards, the process card and render.page build their HTML from these. This module imports
nothing from dossier.render, so any module of the package below render.page may import it at the top.
"""
from __future__ import annotations

import html
import re

__all__ = [
    "AFTER_PREP", "BARE_FILE", "CLAUSE_WORD", "E", "EXPAND_ICONS", "FREE_TEXT_WORDS", "INLINE_CITE", "Raw",
    "SEE_TAIL", "SENTENCE_START", "SEV_TONE", "STATUS_STYLE", "TALL_ROWS", "_NW", "_OL_ITEM", "_UL_ITEM", "added_tag",
    "auto_columns", "badge", "basis", "basis_for", "cell_html", "code_files", "gid_tag", "inline", "inline_cites",
    "keep_whole", "lift_cites", "md", "new_cites", "parse_cite", "path_code", "render_table", "sev_badge",
    "source_cell", "stands_for_name", "stat_sub", "stats_html", "status_badge", "user_note",
]


INLINE_CITE = re.compile(r"\[\[(.+?)\]\]")

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)


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


_UL_ITEM = re.compile(r"^\s*[-*] ")
_OL_ITEM = re.compile(r"^\s*\d+[.)] ")


def md(text, refs):
    out = []
    for para in re.split(r"\n\s*\n", str(text or "").strip()):
        lines = [l for l in para.split("\n") if l.strip()]
        if lines and all(_UL_ITEM.match(l) for l in lines):
            out.append("<ul>" + "".join(f"<li>{inline(_UL_ITEM.sub('', l), refs)}</li>" for l in lines) + "</ul>")
        elif lines and all(_OL_ITEM.match(l) for l in lines):
            out.append("<ol>" + "".join(f"<li>{inline(_OL_ITEM.sub('', l), refs)}</li>" for l in lines) + "</ol>")
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


def added_tag(node):
    """The pill on a row or entry that Claude found and no tool listed."""
    return badge("added by Claude", "", "outline") if isinstance(node, dict) and node.get("added") else ""


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


def status_badge(v):
    cls, variant = STATUS_STYLE.get(str(v).strip().lower(), ("", "outline"))
    return badge(v, cls, variant)


_NW = re.compile(r"\d{4}-\d{2}-\d{2}|[\w.]+(?:-[\w.]+)*\[bot\]|\b[A-Za-z]+-\d\w*")


def keep_whole(h):
    """Stop dates and bot names breaking at their hyphens (text outside tags only)."""
    return "".join(seg if seg.startswith("<") else _NW.sub(lambda m: f'<span class="nw">{m.group(0)}</span>', seg) for seg in re.split(r"(<[^>]*>)", h))


def cell_html(cell, refs):
    if refs.cites.path_like(cell):
        return f'<code>{E(str(cell).strip()).replace("/", "/<wbr>")}</code>'
    return keep_whole(inline(cell, refs))


FREE_TEXT_WORDS = 12  # a cell of more words than this is free text: its citations stay where the author put them


def lift_cites(cell, refs):
    """(cell, citations) for a table cell. A short cell gives its inline citations to the Source column: a marker with a label
    or one that stands where a file name belongs is replaced by that name in code, any other marker is dropped. A cell of free text is left as it is."""
    text = str(cell or "")
    if not INLINE_CITE.search(text):
        return text, []
    text = SEE_TAIL.sub(r"\1", text)
    if len(INLINE_CITE.sub("", text).split()) > FREE_TEXT_WORDS:
        return text, []
    lifted = []

    def sub(m):
        raw, _, label = m.group(1).partition("|")
        raws = [x.strip() for x in raw.split(", ") if x.strip()]
        lifted.extend(raws)
        label = label.strip()
        if not label and len(raws) == 1 and parse_cite(raws[0])["kind"] == "file" and stands_for_name(m.string[:m.start()], m.string[m.end():]):
            label = parse_cite(raws[0])["path"]
        return f"`{label}`" if label else ""
    out = INLINE_CITE.sub(sub, text)
    return re.sub(r"\s+([.,;:])", r"\1", re.sub(r"[ \t]{2,}", " ", out)).strip(), lifted


TALL_ROWS = 40  # a longer table scrolls inside its card; every row stays in the page


def auto_columns(columns):
    """The two headings render adds to an authored table: (basis, citations). A schema column of the same name gets the other word."""
    have = {c.strip().lower() for c in columns}
    return ("Confidence" if "basis" in have else "Basis", "Citations" if "source" in have else "Source")


def render_table(columns, rows, refs, tid, filterable=True, plain=False, group=None, foot=None, sort=True, cls=""):
    """rows are dicts with cells/conf/cite/note (authored) or plain lists of ready HTML (measured)."""
    head = "".join(f"<th>{E(c)}</th>" for c in columns)
    if not plain:
        basis_h, cite_h = auto_columns(columns)
        head += f'<th class="basis-cell">{basis_h}</th><th class="src-cell">{cite_h}</th>'
    body = []
    for r in rows:
        if isinstance(r, dict) and "band" in r:      # a full-width heading row that groups the rows after it
            body.append(f'<tr class="band-row"><td colspan="{len(columns)}">{r["band"]}</td></tr>')
            continue
        if plain:
            body.append("<tr>" + "".join(f'<td data-sort="{E(c[1])}">{keep_whole(str(c[0]))}</td>' if isinstance(c, tuple) else f"<td>{keep_whole(str(c))}</td>" for c in r) + "</tr>")
            continue
        tds, cells, lifted = [], [], []
        for cell in r["cells"]:
            text, found = lift_cites(cell, refs)
            cells.append(text)
            lifted += found
        for col, cell in zip(columns, cells):
            kind = col.strip().lower()
            tds.append(f"<td>{sev_badge(cell)}</td>" if kind == "severity" else f"<td>{status_badge(cell)}</td>" if kind == "status" else f"<td>{cell_html(cell, refs)}</td>")
        note = f'<div class="muted">{inline(r.get("note"), refs)}</div>' if r.get("note") and r.get("conf") != "confirmed" else ""
        cites_ = new_cites(list(r.get("cite") or []) + lifted, *cells)
        body.append("<tr>" + "".join(tds) + f'<td class="basis-cell">{basis_for(r)}{added_tag(r)}{gid_tag(r)}{note}{user_note(r.get("user"))}</td><td class="src-cell">{refs.mark(cites_)}</td></tr>')
    flt = f'<input class="input tbl-filter" type="search" data-target="{tid}" placeholder="Filter rows" aria-label="Filter rows">' if filterable and len(rows) > 6 else ""
    grp_attr = ' class="grp"'
    top = ('<tr class="group-row">' + "".join(f'<th colspan="{n}"{grp_attr if lbl else ""}>{E(lbl)}</th>' for lbl, n in group) + "</tr>") if group else ""
    tf = f'<tfoot><tr class="total-row">{"".join(f"<td>{c}</td>" for c in foot)}</tr></tfoot>' if foot else ""
    return f'{flt}<div class="table-container{" tall" if len(rows) > TALL_ROWS else ""}"><table class="table{" " + cls if cls else ""}" id="{tid}"{"" if sort else " data-nosort"}><thead>{top}<tr>{head}</tr></thead><tbody>{"".join(body)}</tbody>{tf}</table></div>'


EXPAND_ICONS = ('<svg class="ic-max" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="m21 3-7 7"/><path d="m3 21 7-7"/></svg>'
                '<svg class="ic-min" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m14 10 7-7"/><path d="M20 10h-6V4"/><path d="m3 21 7-7"/><path d="M4 14h6v6"/></svg>')


def path_code(path):
    """A file or folder name in code, with no citation after it: the citation goes in the table's Source column."""
    return f"<code>{E(path).replace('/', '/<wbr>')}</code>"


def source_cell(refs, *places):
    """The Source column of a measured row: one numbered marker for each (path, line or None), without repeats."""
    return refs.mark([f"{p}:{n}" if n else p for p, n in places])


class Raw(str):
    """Markup that is already safe to place in the page."""


def stat_sub(s):
    return f'<div class="s">{E(s)}</div>' if s else ""


def stats_html(items):
    cols = 3 if len(items) in (6, 9) else 4 if len(items) == 8 else min(len(items), 5)
    return f'<div class="stats" style="grid-template-columns:repeat({cols},minmax(0,1fr))">' + "".join(
        f'<div class="stat {extra[0] if extra else ""}"><div class="k">{k if isinstance(k, Raw) else E(k)}</div><div class="v">{v if isinstance(v, Raw) else E(v)}</div>{stat_sub(s)}</div>' for k, v, s, *extra in items) + "</div>"
