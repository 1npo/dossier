"""Environment-variable reads and credential-shaped strings, found by pattern matching on file text (post-v1 items 17 and 18).

Nothing here caps a list. A matched credential's text is never kept: `secrets` returns the line and the pattern name only,
and a default that could be a credential is withheld (`SECRET_DEFAULT`).
"""
from __future__ import annotations

import bisect
import re

NAME = r"[A-Za-z_][A-Za-z0-9_]*"

# (language, regex). Group "name" is the variable; `call` forms leave the text after the closing quote for `_default`.
READ_FORMS = [
    ("py", re.compile(r"""\bos\.environ(?:\.get)?\s*[\[(]\s*["'](?P<name>%s)["']""" % NAME)),
    ("py", re.compile(r"""\bos\.getenv\s*\(\s*["'](?P<name>%s)["']""" % NAME)),
    ("js", re.compile(r"""\bprocess\.env\.(?P<name>%s)""" % NAME)),
    ("js", re.compile(r"""\bprocess\.env\[\s*["'](?P<name>%s)["']\s*\]""" % NAME)),
    ("js", re.compile(r"""\bimport\.meta\.env\.(?P<name>%s)""" % NAME)),
    ("js", re.compile(r"""\bimport\.meta\.env\[\s*["'](?P<name>%s)["']\s*\]""" % NAME)),
    ("js", re.compile(r"""\bDeno\.env\.get\(\s*["'](?P<name>%s)["']\s*\)""" % NAME)),
    ("cs", re.compile(r"""\bEnvironment\.GetEnvironmentVariable\(\s*"(?P<name>%s)"\s*\)""" % NAME)),
    ("other", re.compile(r"""\bos\.Getenv\(\s*"(?P<name>%s)"|\bSystem\.getenv\(\s*"(?P<n2>%s)"|\bstd::env::var\(\s*"(?P<n3>%s)"|\bENV\[\s*["'](?P<n4>%s)["']|\bENV\.fetch\(\s*["'](?P<n5>%s)["']"""
                         % ((NAME,) * 5))),
    ("other", re.compile(r"""[^\w.]getenv\(\s*["'](?P<name>%s)["']""" % NAME)),
    ("other", re.compile(r"""\bstd\.(?:posix\.getenv|process\.getEnvVar(?:Owned|Map)?)\(\s*(?:[\w.]+\s*,\s*)?"(?P<name>%s)\"""" % NAME)),
]
DOTENV = re.compile(r"^\s*(?:export\s+)?(?P<name>%s)\s*=" % NAME, re.M)
LITERAL = r"""(?:"(?P<dq>[^"\\\n]*)"|'(?P<sq>[^'\\\n]*)'|(?P<num>-?\d+(?:\.\d+)?)|(?P<kw>True|False|None|true|false|null))"""
# What follows a read: `, "d")` inside the call, or `or "d"`, `|| "d"`, `?? "d"` after it.
IN_CALL = re.compile(r"""\s*,\s*%s\s*\)""" % LITERAL)
AFTER = re.compile(r"""\s*\)?\s*(?:\|\||\?\?|\bor\b)\s*%s""" % LITERAL)

SECRET_PATTERNS = [
    ("aws-access-key-id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("private-key-block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("stripe-live-key", re.compile(r"\b[sr]k_live_[0-9A-Za-z]{20,}\b")),
    ("jwt-like", re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}")),
]
SECRET_DEFAULT = re.compile(r"(key|secret|token|passw(or)?d|pwd|credential|auth|private)", re.I)
MAX_DEFAULT = 80


class Lines:
    """Line number of a text offset, computed once per file and only when asked."""

    def __init__(self, text):
        self.text, self._nl = text, None

    def at(self, pos):
        if self._nl is None:
            self._nl = [i for i, c in enumerate(self.text) if c == "\n"]
        return bisect.bisect_left(self._nl, pos) + 1


def _default(text, end, name):
    """The literal default a read carries, as text, or None. A default that may be a credential is withheld."""
    for form in (IN_CALL, AFTER):
        m = form.match(text, end)
        if m:
            val = next((m.group(k) for k in ("dq", "sq", "num", "kw") if m.group(k) is not None), None)
            if val is None:
                return None
            if SECRET_DEFAULT.search(name) or any(p.search(val) for _, p in SECRET_PATTERNS):
                return "(withheld: may be a credential)"
            return val[:MAX_DEFAULT]
    return None


def reads(text, lines=None):
    """[{name, line, default?}] for every read of an environment variable in `text`, in file order."""
    lines = lines or Lines(text)
    out = []
    for _, rx in READ_FORMS:
        for m in rx.finditer(text):
            name = next(v for k, v in m.groupdict().items() if v and (k == "name" or k.startswith("n")))
            site = {"name": name, "line": lines.at(m.start())}
            d = _default(text, m.end(), name)
            if d is not None:
                site["default"] = d
            out.append(site)
    return sorted(out, key=lambda s: (s["line"], s["name"]))


def dotenv(text, lines=None):
    """[{name, line}] for every `NAME=` line of a `.env`-style file. Values are not read."""
    lines = lines or Lines(text)
    return [{"name": m.group("name"), "line": lines.at(m.start())} for m in DOTENV.finditer(text)]


def secrets(text, lines=None):
    """[{line, kind}] for every line that matches a credential pattern. The matched text is dropped here."""
    lines = lines or Lines(text)
    out = []
    for kind, rx in SECRET_PATTERNS:
        out += [{"line": lines.at(m.start()), "kind": kind} for m in rx.finditer(text)]
    return sorted(out, key=lambda h: (h["line"], h["kind"]))


INFRA = re.compile(r"(^|/)(Dockerfile[^/]*|[^/]*\.dockerfile|(docker-)?compose[^/]*\.ya?ml|\.github/workflows/[^/]+\.ya?ml|\.gitlab-ci\.ya?ml|\.circleci/config\.ya?ml"
                   r"|Jenkinsfile|azure-pipelines[^/]*\.ya?ml|\.env(\.[^/]+)?)$")
WORD = re.compile(NAME)


def is_infra(path):
    return bool(INFRA.search(path)) or path.startswith(".github/workflows/")


def declared_in(path, text):
    """The set of names a Dockerfile, compose file, CI workflow or `.env` file mentions, to match against the names the code reads."""
    return set(WORD.findall(text))
