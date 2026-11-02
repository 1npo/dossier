"""The repository-wide adapter: what belongs to no single language.

Entry points from Dockerfiles, Makefiles, CI files, systemd units and shebang scripts; SQL tables and migrations;
CI test commands; and the language-independent blind-spot scan (`rules/all`).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import gather
from adapters import Adapter

RULES_ALL = Path(__file__).resolve().parent.parent / "rules" / "all"
MAX_BYTES = 1_000_000
TEST_COMMAND = re.compile(r"\b(pytest|tox|nox)\b|make test\b")
NOT_COLUMN = ("primary", "foreign", "constraint", "unique", "key", "check", "index", "exclude")
TRIGGERS = {"container": "When the container starts", "make-target": "Running `make {name}`", "ci-schedule": "On the schedule `{name}`",
            "shebang-script": "When the script is run", "systemd-unit": "When the system service starts"}


def entry(path: str, line: int, kind: str, name: str, target: str, snippet: str) -> dict:
    return {"path": path, "line": line, "end_line": line, "kind": kind, "name": name, "trigger": TRIGGERS[kind].format(name=name),
            "target": target, "rule": "repo." + kind, "snippet": snippet.strip()[:200]}


def dockerfile_entries(path: str, text: str) -> list:
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        m = re.match(r"\s*(CMD|ENTRYPOINT)\s+(.+)$", line, re.I)
        if m:
            found.append(entry(path, n, "container", m.group(1).upper(), m.group(2).strip(), line))
    return found


def makefile_targets(path: str, text: str) -> list:
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        m = re.match(r"([A-Za-z0-9_][A-Za-z0-9_.-]*):(?!=)", line)
        if m:
            found.append(entry(path, n, "make-target", m.group(1), "make " + m.group(1), line))
    return found


def _strip_comment(value: str) -> str:
    return re.sub(r"\s+#.*$", "", value).strip().strip("\"'")


def workflow_entries(path: str, text: str) -> list:
    """`ci-schedule` entry points and `ci-command` test commands from a GitHub or GitLab CI file."""
    found, lines, block_indent = [], text.splitlines(), None
    for n, line in enumerate(lines, 1):
        indent = len(line) - len(line.lstrip())
        if block_indent is not None:
            if line.strip() and indent <= block_indent:
                block_indent = None
            elif TEST_COMMAND.search(line):
                found.append({"kind": "ci-command", "path": path, "line": n, "command": _strip_comment(line.strip()), "rule": "repo.ci-command"})
                continue
        cron = re.search(r"cron:\s*(.+)$", line)
        if cron:
            found.append(entry(path, n, "ci-schedule", _strip_comment(cron.group(1)), _strip_comment(cron.group(1)), line))
            continue
        run = re.match(r"\s*(?:-\s+)?run:\s*(.*)$", line)
        item = re.match(r"\s*-\s+(?!cron:|run:)(.+)$", line) if path.endswith(".gitlab-ci.yml") else None
        value = run.group(1) if run else item.group(1) if item else ""
        if run and value.strip() in ("|", ">", "|-", ">-"):
            block_indent = indent
        elif TEST_COMMAND.search(value):
            found.append({"kind": "ci-command", "path": path, "line": n, "command": _strip_comment(value), "rule": "repo.ci-command"})
    return found


def systemd_units(path: str, text: str) -> list:
    for n, line in enumerate(text.splitlines(), 1):
        m = re.match(r"\s*ExecStart=(.+)$", line)
        if m:
            return [entry(path, n, "systemd-unit", Path(path).name, m.group(1).strip(), line)]
    return []


def shebang_scripts(path: str, text: str) -> list:
    first = text.splitlines()[0] if text else ""
    return [entry(path, 1, "shebang-script", Path(path).name, first[2:].strip(), first)] if first.startswith("#!") else []


def _columns(body: str, first_line: int) -> list:
    """Columns from the text between the parentheses of CREATE TABLE; `first_line` is the line the text starts on."""
    parts, depth, cur, begin = [], 0, "", 0
    for i, ch in enumerate(body + ","):
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            parts.append((cur, begin))
            cur, begin = "", i + 1
        else:
            cur += ch
    fields = []
    for part, offset in parts:
        words = part.split()
        if not words or words[0].lower().strip('"`') in NOT_COLUMN:
            continue
        ref = re.search(r"references\s+[\"`]?(\w+)", part, re.I)
        lead = len(part) - len(part.lstrip())
        fields.append({"name": words[0].strip('"`'), "type": words[1] if len(words) > 1 else None,
                       "line": first_line + body[: offset + lead].count("\n"), "ref": ref.group(1) if ref else None})
    return fields


def sql_tables(path: str, text: str) -> list:
    """`sql-table` entities from CREATE TABLE statements; a .sql file in a migrations folder is one `migration` item instead."""
    if re.search(r"(^|/)migrations/", path):
        return [{"path": path, "kind": "migration", "tool": "sql", "rule": "repo.migration"}]
    found = []
    for m in re.finditer(r"create\s+table\s+(?:if\s+not\s+exists\s+)?[\"`]?([\w.]+)[\"`]?\s*\(", text, re.I):
        depth, i = 1, m.end()
        while i < len(text) and depth:
            depth += (text[i] == "(") - (text[i] == ")")
            i += 1
        first = text.count("\n", 0, m.start()) + 1
        snippet = text[m.start():].splitlines()[0].strip()[:200]
        found.append({"path": path, "line": first, "end_line": text.count("\n", 0, i) + 1, "name": m.group(1).split(".")[-1],
                      "kind": "sql-table", "rule": "repo.sql-table", "snippet": snippet, "bases": [],
                      "fields": _columns(text[m.end():i - 1], text.count("\n", 0, m.end()) + 1)})
    return found


def _is_dockerfile(base: str) -> bool:
    return base.startswith("Dockerfile") or base.endswith(".Dockerfile") or base == "Containerfile"


def _read(checkout: Path, rel: str):
    f = checkout / rel
    try:
        return f.read_text(encoding="utf-8") if f.stat().st_size <= MAX_BYTES else None
    except (OSError, UnicodeDecodeError):
        return None


def _executable_files(checkout: Path, sha: str) -> list:
    r = subprocess.run(["git", "-C", str(checkout), "ls-tree", "-r", sha], capture_output=True, text=True)
    if r.returncode != 0:
        return []
    return [line.split("\t", 1)[1] for line in r.stdout.splitlines() if line.startswith("100755 ")]


class RepoAdapter(Adapter):
    name = "repo"
    version = "1"
    languages = ("*",)
    tools = ("semgrep",)

    def extract(self, ctx) -> dict:
        out = {"entry_points": [], "models": [], "tests": [], "blindspots": []}
        executable = set(_executable_files(ctx.checkout, ctx.sha))
        for path in sorted(ctx.tree):
            if gather.noise_reason(path):
                continue
            base, found = path.rsplit("/", 1)[-1], []
            text = None
            if _is_dockerfile(base) or base in ("Makefile", "makefile", "GNUmakefile") or base.endswith((".mk", ".service", ".sql")) \
                    or re.search(r"(^|/)\.github/workflows/[^/]+\.ya?ml$", path) or base == ".gitlab-ci.yml" or path in executable:
                text = _read(ctx.checkout, path)
            if text is None:
                continue
            if _is_dockerfile(base):
                found = dockerfile_entries(path, text)
            elif base in ("Makefile", "makefile", "GNUmakefile") or base.endswith(".mk"):
                found = makefile_targets(path, text)
            elif base == ".gitlab-ci.yml" or "/.github/workflows/" in "/" + path:
                found = workflow_entries(path, text)
            elif base.endswith(".service"):
                found = systemd_units(path, text)
            elif base.endswith(".sql"):
                out["models"] += sql_tables(path, text)
            if path in executable and not found:
                found = shebang_scripts(path, text)
            for it in found:
                out["tests" if it["kind"] == "ci-command" else "entry_points"].append(it)
        code = [p for p in sorted(ctx.tree) if not gather.noise_reason(p) and (gather.lang_of(p) or (None, None))[1] == "code"]
        try:
            for r in (ctx.semgrep.scan(RULES_ALL, code) if code else []):
                out["blindspots"].append({"path": r["path"], "line": r["start_line"], "end_line": r["end_line"],
                                          "pattern": r["metadata"].get("pattern"), "rule": r["rule"], "snippet": r["snippet"]})
            ctx.tool_status["semgrep"] = {"status": "ok", "reason": None}
        except Exception as e:  # the other outputs are still good
            ctx.tool_status["semgrep"] = {"status": "failed", "reason": (str(e).splitlines() or [type(e).__name__])[0]}
        return out
