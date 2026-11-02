# /// script
# requires-python = ">=3.10"
# dependencies = ["tree-sitter-language-pack==1.22.1"]
# ///
"""Tree-sitter worker: reads one JSON request on stdin, prints one JSON response on stdout.

Request:  {"language": "python", "paths": ["a.py"], "query": "(call function: (identifier) @fn)"}
Response: {"matches": [{"path", "capture", "start_line", "start_col", "end_line", "end_col", "text"}],
           "errors": [{"path", "error"}]}
Lines are 1-based, columns 0-based. Paths are relative to the current directory.
Each file is parsed in a child process, and matches come from `QueryCursor.matches`: tree-sitter 0.25's `captures` corrupts memory
on some real files (found on a real repository, M2 sign-off) and a crash would otherwise lose the whole batch. A file whose child
still dies is reported in `errors` and skipped.
Grammars are cached next to the shared uv cache (UV_CACHE_DIR's parent), not in the real home folder.
"""
import json
import os
import sys
from pathlib import Path

import tree_sitter as ts
import tree_sitter_language_pack as pack


def file_matches(parser, query, path: str, data: bytes) -> list:
    tree = parser.parse(data)
    out = []
    for _, caps in ts.QueryCursor(query).matches(tree.root_node):
        for name, nodes in caps.items():
            for n in nodes:
                out.append({"path": path, "capture": name, "start_line": n.start_point.row + 1,
                            "start_col": n.start_point.column, "end_line": n.end_point.row + 1,
                            "end_col": n.end_point.column, "text": data[n.start_byte:n.end_byte].decode("utf-8", "replace")})
    return out


def in_child(work) -> tuple:
    """(result, error): run `work()` in a forked child and read its JSON result from a pipe. A crash gives ([], reason)."""
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:  # child
        status = 1
        try:
            os.close(read_fd)
            with os.fdopen(write_fd, "w") as w:
                json.dump(work(), w)
            status = 0
        finally:
            os._exit(status)
    os.close(write_fd)
    with os.fdopen(read_fd) as r:
        raw = r.read()
    _, code = os.waitpid(pid, 0)
    if code != 0:
        return [], f"tree-sitter stopped on this file ({'signal ' + str(os.WTERMSIG(code)) if os.WIFSIGNALED(code) else 'exit ' + str(os.WEXITSTATUS(code))}); it was skipped"
    return json.loads(raw), None


def main() -> None:
    req = json.load(sys.stdin)
    cache = os.environ.get("UV_CACHE_DIR")
    base = Path(cache).parent / "grammars" if cache else Path(os.environ.get("XDG_CACHE_HOME", ".")) / "grammars"
    pack.configure(pack.PackConfig(cache_dir=str(base)))
    lang = pack.get_language(req["language"])
    parser = pack.get_parser(req["language"])
    query = ts.Query(lang, req["query"])
    matches, errors = [], []
    for path in req["paths"]:
        try:
            data = Path(path).read_bytes()
        except OSError as e:
            errors.append({"path": path, "error": str(e)})
            continue
        found, error = in_child(lambda: file_matches(pack.get_parser(req["language"]), query, path, data))
        matches += found
        if error:
            errors.append({"path": path, "error": error})
    matches.sort(key=lambda m: (m["path"], m["start_line"], m["start_col"], m["capture"]))
    json.dump({"matches": matches, "errors": errors}, sys.stdout)


if __name__ == "__main__":
    main()
