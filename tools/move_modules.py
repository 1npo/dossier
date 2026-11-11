#!/usr/bin/env python3
"""Move flat modules from scripts/ into the dossier package and rewrite every import of them (plan 014, A3).

  python3 tools/move_modules.py MAP [--dry-run] [--check]

MAP has one move per line, `old_flat_name new.dotted.module` (relative to the `dossier` package), and `#`
comments. For each line the tool runs `git mv scripts/<old>.py src/dossier/<new as path>.py`, creating the
folders, and gives every new package folder an `__init__.py` (a one-line docstring and an empty `__all__`).

Then, in every tracked `*.py` under src/, scripts/, tests/ (not tests/fixtures/) and tools/, it finds with
`ast` each `import` and level-0 `from ... import` of an old name, at any depth, and replaces only that
statement's source, keeping the name the code binds:

  import old             ->  from dossier.<pkg> import <leaf>  (or `... import <leaf> as old` when they differ)
  import old as x        ->  from dossier.<pkg> import <leaf> as x   (no `as` when leaf == x)
  import a, old, b       ->  one statement per name, each on its own line at the same indentation
  from old import names  ->  only the module token changes; parentheses and line breaks are kept

A trailing comment (`# noqa: E402`) is kept on every line a statement becomes. String literals and attribute
expressions are never touched. `--dry-run` prints the rewrites and changes nothing. `--check` changes nothing
and exits 1, listing file and line, if any level-0 import of an old name is left.

The tool refuses to run if the tree is dirty (a dry run allows it), a source file is missing or a destination
exists.
Standard library only; run it from the repository root.
"""
from __future__ import annotations

import argparse
import ast
import io
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path

PACKAGE = "dossier"
SCOPES = ("src/", "scripts/", "tests/", "tools/")
SKIP = ("tests/fixtures/",)

# The docstring of each new package's __init__.py (plan 014, D4 "Holds"); F5 expands them.
DOCS = {
    "core": "Leaf utilities with no domain knowledge: config file, build log, graph helpers, card schema loader, SCIP reader.",
    "facts": "Deterministic facts about the repository at the pin: files, languages, manifests, dependencies, environment reads, markers.",
    "tooling": "Running things on the host: which tools exist, the safe runner, the locked-worker clients, the .NET SDK check.",
    "findings": "The component model, candidate findings with stable ids, people figures, open items and decisions.",
    "history": "The whole git history folded once: per-file, per-pair, per-person figures, ownership, approvals, workflow.",
    "adapters": "Turning one language's code into the standard outputs.",
    "render": "The page: citations and markup, measured cards, the process card, viewer, portfolio, summary.json.",
    "checks": "V2 to V7 and V11 to V12, and --verify sampling.",
    "pipeline": "The prepare stages: work area, restore, the extract runner, incremental planning.",
    "cli": "Argument parsing and one module per command group.",
    "adapters.python": "The Python adapter and its helpers.",
    "adapters.js": "The JavaScript and TypeScript adapter and its helpers.",
    "adapters.csharp": "The C# adapter and its helpers.",
    "render.measured": "The measured cards: drawn by code from extract/, never written by Claude.",
    "cli.commands": "One module per group of CLI commands.",
}


class MoveError(Exception):
    pass


@dataclass(frozen=True)
class Move:
    old: str  # flat module name in scripts/
    new: str  # dotted module path inside the package, e.g. "cli.app"

    @property
    def parent(self) -> str:
        """The full dotted package the module lands in, e.g. `dossier.cli`."""
        return ".".join([PACKAGE, *self.new.split(".")[:-1]])

    @property
    def leaf(self) -> str:
        return self.new.split(".")[-1]

    @property
    def full(self) -> str:
        return f"{PACKAGE}.{self.new}"

    @property
    def source(self) -> Path:
        return Path("scripts") / f"{self.old}.py"

    @property
    def dest(self) -> Path:
        return Path("src") / PACKAGE / Path(*self.new.split(".")).with_suffix(".py")


def parse_map(text: str) -> dict[str, Move]:
    moves: dict[str, Move] = {}
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2 or not all(p.replace("_", "a").replace(".", "a").isalnum() for p in parts) or "." in parts[0]:
            raise MoveError(f"map line {n}: expected `old_flat_name new.dotted.module`, got {raw!r}")
        if parts[0] in moves:
            raise MoveError(f"map line {n}: {parts[0]} is mapped twice")
        moves[parts[0]] = Move(*parts)
    return moves


# ---------------------------------------------------------------- rewriting


def _line_starts(text: str) -> list[int]:
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _offset(starts: list[int], text: str, lineno: int, col: int) -> int:
    """Character offset of (1-based line, UTF-8 byte column) as ast reports it."""
    start = starts[lineno - 1]
    line = text[start:text.find("\n", start) if text.find("\n", start) != -1 else len(text)]
    return start + len(line.encode("utf-8")[:col].decode("utf-8"))


def _comments(text: str) -> dict[int, str]:
    """1-based line -> the comment token on it."""
    out = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                out[tok.start[0]] = tok.string
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return out


def _alias_import(move: Move, bound: str) -> str:
    return f"from {move.parent} import {move.leaf}" + ("" if bound == move.leaf else f" as {bound}")


def _skip_package_import(node: ast.ImportFrom, moves: dict[str, Move]) -> bool:
    """`from dossier import x` names the package itself once a move of `dossier` has run: leave it."""
    if node.module != PACKAGE or PACKAGE not in moves:
        return False
    pkg = Path("src") / PACKAGE
    return all((pkg / f"{a.name}.py").is_file() or (pkg / a.name).is_dir() for a in node.names)


def matches(node: ast.AST, moves: dict[str, Move]) -> bool:
    if isinstance(node, ast.Import):
        return any(a.name in moves for a in node.names)
    if isinstance(node, ast.ImportFrom):
        return node.level == 0 and node.module in moves and not _skip_package_import(node, moves)
    return False


def rewrite(text: str, moves: dict[str, Move]) -> tuple[str, list[tuple[int, str, str]]]:
    """(new text, [(line, old statement, new statement)]) for one file's source."""
    tree = ast.parse(text)
    starts = _line_starts(text)
    comments = _comments(text)
    edits = []
    for node in ast.walk(tree):
        if not matches(node, moves):
            continue
        a = _offset(starts, text, node.lineno, node.col_offset)
        b = _offset(starts, text, node.end_lineno, node.end_col_offset)
        old = text[a:b]
        if isinstance(node, ast.ImportFrom):
            move = moves[node.module]
            head = old.find(node.module, len("from"))
            new = old[:head] + move.full + old[head + len(node.module):]
        else:
            parts = []
            for alias in node.names:
                if alias.name in moves:
                    parts.append(_alias_import(moves[alias.name], alias.asname or alias.name))
                else:
                    parts.append(f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else ""))
            line_start = starts[node.lineno - 1]
            indent = text[line_start:a]
            alone = indent.strip() == "" and text[b:].split("\n", 1)[0].strip() in ("", comments.get(node.end_lineno, ""))
            if alone:
                comment = comments.get(node.end_lineno)
                tail = f"  {comment}" if comment and len(parts) > 1 else ""
                new = (tail + "\n" + indent).join(parts)
            else:
                new = "; ".join(parts)
        edits.append((a, b, node.lineno, old, new))
    out = text
    for a, b, _, _, new in sorted(edits, key=lambda e: e[0], reverse=True):
        out = out[:a] + new + out[b:]
    return out, [(line, old, new) for _, _, line, old, new in sorted(edits, key=lambda e: e[0])]


def leftovers(text: str, moves: dict[str, Move]) -> list[int]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    return sorted(node.lineno for node in ast.walk(tree) if matches(node, moves))


# ---------------------------------------------------------------- the repository


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def tracked_python() -> list[Path]:
    files = _git("ls-files", "-z", "--", "*.py").split("\0")
    return [Path(f) for f in files if f and f.startswith(SCOPES) and not f.startswith(SKIP) and Path(f).is_file()]


def preflight(moves: dict[str, Move], *, dry_run: bool = False) -> None:
    if not dry_run and _git("status", "--porcelain").strip():
        raise MoveError("the working tree is dirty; commit or stash first")
    for m in moves.values():
        if not m.source.is_file():
            raise MoveError(f"{m.source} does not exist")
        if m.dest.exists():
            raise MoveError(f"{m.dest} already exists")


def init_text(package: str) -> str:
    doc = DOCS.get(package, f"The {package} package.")
    return f'"""{doc}"""\n\n__all__: list[str] = []\n'


def new_packages(moves: dict[str, Move]) -> list[Path]:
    """Every package folder a move lands in that has no __init__.py yet, outermost first."""
    out = []
    for m in moves.values():
        parts = m.new.split(".")[:-1]
        for i in range(1, len(parts) + 1):
            init = Path("src") / PACKAGE / Path(*parts[:i]) / "__init__.py"
            if not init.exists() and init not in out:
                out.append(init)
    root = Path("src") / PACKAGE / "__init__.py"
    if not root.exists():
        out.insert(0, root)
    return sorted(out, key=lambda p: len(p.parts))


def run(moves: dict[str, Move], *, dry_run: bool) -> int:
    preflight(moves, dry_run=dry_run)
    files = tracked_python()
    changes = []
    for f in files:
        text = f.read_text()
        new, edits = rewrite(text, moves)
        if edits:
            changes.append((f, new, edits))
    for f, _, edits in changes:
        for line, old, new in edits:
            print(f"{f}:{line}: {old!r} -> {new!r}")
    if dry_run:
        for m in moves.values():
            print(f"move {m.source} -> {m.dest}")
        for init in new_packages(moves):
            print(f"create {init}")
        return 0
    for init in new_packages(moves):
        init.parent.mkdir(parents=True, exist_ok=True)
        package = ".".join(init.parent.parts[2:]) or PACKAGE
        init.write_text(init_text(package))
    for f, new, _ in changes:
        f.write_text(new)
    for m in moves.values():
        m.dest.parent.mkdir(parents=True, exist_ok=True)
        _git("mv", str(m.source), str(m.dest))
    _git("add", "--", *[str(p) for p in Path("src", PACKAGE).rglob("__init__.py")])
    print(f"moved {len(moves)} module(s), rewrote {sum(len(e) for _, _, e in changes)} import(s) in {len(changes)} file(s)")
    return 0


def check(moves: dict[str, Move]) -> int:
    bad = [(f, line) for f in tracked_python() for line in leftovers(f.read_text(), moves)]
    for f, line in bad:
        print(f"{f}:{line}: import of a moved module")
    return 1 if bad else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="move_modules.py", description=__doc__.split("\n\n")[0])
    p.add_argument("map", help="file of `old_flat_name new.dotted.module` lines")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="print the rewrites; change nothing")
    g.add_argument("--check", action="store_true", help="exit 1 if any import of an old name is left")
    a = p.parse_args(argv)
    try:
        moves = parse_map(Path(a.map).read_text())
        return check(moves) if a.check else run(moves, dry_run=a.dry_run)
    except MoveError as e:
        print(f"move_modules: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
