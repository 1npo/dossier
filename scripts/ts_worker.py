# /// script
# requires-python = ">=3.10"
# dependencies = ["tree-sitter-language-pack==1.22.1", "tree-sitter==0.25.2"]
# ///
"""Tree-sitter worker: reads one JSON request on stdin, prints one JSON response on stdout.

Request:  {"language": "python", "paths": ["a.py"], "query": "(call function: (identifier) @fn)"}
Response: {"matches": [{"path", "capture", "start_line", "start_col", "end_line", "end_col", "text"}],
           "errors": [{"path", "error"}]}
Lines are 1-based, columns 0-based. Paths are relative to the current directory.
tree-sitter is pinned to 0.25.2: 0.26.0 (what the language pack otherwise resolves to) corrupts memory while iterating query
results and segfaulted on 10 of 106 files of a real repository (found at the M2 sign-off; 0.25.0 and 0.25.2 are clean).
Grammars are cached next to the shared uv cache (UV_CACHE_DIR's parent), not in the real home folder.
"""
import json
import os
import sys
from pathlib import Path

import tree_sitter as ts
import tree_sitter_language_pack as pack


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
        tree = parser.parse(data)
        caps = ts.QueryCursor(query).captures(tree.root_node)
        for name, nodes in caps.items():
            for n in nodes:
                matches.append({"path": path, "capture": name, "start_line": n.start_point.row + 1,
                                "start_col": n.start_point.column, "end_line": n.end_point.row + 1,
                                "end_col": n.end_point.column, "text": n.text.decode("utf-8", "replace")})
    matches.sort(key=lambda m: (m["path"], m["start_line"], m["start_col"], m["capture"]))
    json.dump({"matches": matches, "errors": errors}, sys.stdout)


if __name__ == "__main__":
    main()
