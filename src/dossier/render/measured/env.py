"""The environment-variable and secret-signal cards of report `ops` (post-v1 items 17 and 18), drawn from the gatherer's facts.

Both cards list every row (no caps; the page sorts and filters). The secrets card never prints or stores a matched value: the facts
hold the path, line and pattern name only.
"""
from __future__ import annotations

from dossier.render.measured import change as measured_change
from dossier.render import markup

__all__ = ["DRAWN", "ENV_COLUMNS", "SECRET_COLUMNS"]

ENV_COLUMNS = ["Variable", "Read at", "Default", "Also declared in", "Source"]
SECRET_COLUMNS = ["Path", "Line", "Pattern", "Note", "Source"]
SENSITIVE_PATTERN = "sensitive file name"


def _table(cid, columns, rows, refs):
    return markup.render_table(columns, rows, refs, "t-" + cid.replace(".", "-"), plain=True)


def _num(n):
    return (str(n), n)


def env_vars(cid, ctx, refs):
    facts = ctx.get("facts")
    if facts is None or "env_vars" not in facts:
        return None
    rows = []
    for v in facts["env_vars"]:
        sites = v.get("sites") or []
        read = "<br>".join(f"{markup.path_code(s['path'])}:{s['line']}" for s in sites) or '<span class="muted">not read by the code found (declared only)</span>'
        defaults = sorted({s["default"] for s in sites if "default" in s})
        declared = "<br>".join(markup.path_code(p) for p in v.get("declared_in") or []) or '<span class="muted">none</span>'
        places = [(s["path"], s["line"]) for s in sites] or [(v["first"]["path"], v["first"]["line"])]
        rows.append([(f"<code>{markup.E(v['name'])}</code>", v["name"]), read, markup.E(", ".join(defaults)) if defaults else '<span class="muted">none</span>', declared,
                     markup.source_cell(refs, *places)])
    foot = measured_change.foot_notes("Found by pattern matching on the source. A name built at run time, or read through a settings object, is not found.",
                                      "A default is shown only when the call gives a literal one; a default that may be a credential is withheld.")
    head = measured_change.intro("Every environment variable the code reads: where, the default the call gives, and whether a Dockerfile, compose file, CI workflow or .env file also names it.")
    if not rows:
        return head + _table(cid, ENV_COLUMNS, [], refs) + measured_change.none_found("No environment variable reads were found.") + foot
    return head + _table(cid, ENV_COLUMNS, rows, refs) + foot


def secret_signals(cid, ctx, refs):
    facts = ctx.get("facts")
    if facts is None or "secret_signals" not in facts:
        return None
    s = facts["secret_signals"]
    items = [(h["path"], h["line"], h["kind"], "A string in this file matches the pattern. Review it by hand.") for h in s.get("hits") or []]
    items += [(f["path"], 0, SENSITIVE_PATTERN, f.get("verdict", "")) for f in s.get("sensitive_files") or []]
    rows = [[(markup.path_code(p), p), _num(n) if n else '<span class="muted">-</span>', markup.E(kind), markup.E(note), markup.source_cell(refs, (p, n or None))]
            for p, n, kind, note in sorted(items, key=lambda i: (i[0], i[1], i[2]))]
    head = measured_change.intro("This lists pattern matches for human review. It is not a security scanner: a match may be a test value, and a secret in another shape is missed. "
                                 "The matched text is never printed or stored here.")
    if not rows:
        return head + _table(cid, SECRET_COLUMNS, [], refs) + measured_change.none_found("No credential-shaped strings or secret-prone files were found.")
    return head + _table(cid, SECRET_COLUMNS, rows, refs)


DRAWN = {"ops.env-vars": env_vars, "ops.secret-signals": secret_signals}
