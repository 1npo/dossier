"""Tier B symbols: the top-level definitions of languages that have a tree-sitter grammar but no adapter.

Only the definitions are listed (functions, types, modules) as `decl` symbols with path, line and kind. There is no call graph and no
imports, so the `no static graph` badge stays. `decl` is not `def`: the dead-code, duplicate-name and public-API code reads only `def`.
Each language is one query. Add a language by adding a row to `LANGUAGES` and a fixture and test for it.
"""
from __future__ import annotations

from dossier.facts import gather
from dossier.adapters.base import Adapter, failure_reason

PACK = "tree-sitter-language-pack"
# dossier language name -> (grammar name, file extensions to read, query whose captures are the kind of each definition)
LANGUAGES = {
    "Shell": ("bash", ("sh", "bash", "zsh"), "(program (function_definition name: (word) @function))"),
    "Rust": ("rust", ("rs",), "(source_file [(function_item name: (identifier) @function) (struct_item name: (type_identifier) @struct) "
                              "(enum_item name: (type_identifier) @enum) (trait_item name: (type_identifier) @trait) "
                              "(type_item name: (type_identifier) @type) (mod_item name: (identifier) @module)])"),
    "Go": ("go", ("go",), "(source_file [(function_declaration name: (identifier) @function) (method_declaration name: (field_identifier) @method) "
                          "(type_declaration (type_spec name: (type_identifier) @type))])"),
    "Ruby": ("ruby", ("rb", "rake", "gemspec"), "(program [(class name: (constant) @class) (module name: (constant) @module) "
                                                "(method name: (identifier) @function)])"),
    "Java": ("java", ("java",), "(program [(class_declaration name: (identifier) @class) (interface_declaration name: (identifier) @interface) "
                                "(enum_declaration name: (identifier) @enum) (record_declaration name: (identifier) @record)])"),
}


def files_of(language: str, paths) -> list:
    """The tracked, non-noise files of `language` among `paths`, sorted."""
    _, exts, _ = LANGUAGES[language]
    return sorted(p for p in paths if not gather.noise_reason(p) and p.rsplit(".", 1)[-1].lower() in exts and (gather.lang_of(p) or (None,))[0] == language)


def symbols(treesitter, language: str, paths: list) -> list:
    """`decl` symbols for the top-level definitions in `paths`, sorted by path, line, name."""
    grammar, _, query = LANGUAGES[language]
    out = [{"kind": "decl", "path": m["path"], "line": m["start_line"], "name": m["text"], "symbol_kind": m["capture"], "language": language, "via": "tree-sitter"}
           for m in treesitter.query(grammar, paths, query)] if paths else []
    return sorted(out, key=lambda s: (s["path"], s["line"], s["name"]))


class TierBAdapter(Adapter):
    name = "tier-b"
    version = "1"
    languages = tuple(LANGUAGES)
    tools = (PACK,)

    def extract(self, ctx) -> dict:
        out = {"symbols": []}
        found = []
        for language in LANGUAGES:
            paths = files_of(language, ctx.tree)
            if not paths:
                continue
            try:
                out["symbols"] += symbols(ctx.treesitter, language, paths)
            except Exception as e:  # a grammar that fails must not stop the other languages
                found.append((language, failure_reason(e)))
        if found:
            ctx.tool_failed(PACK, "; ".join(f"{n}: {why}" for n, why in found))
        else:
            ctx.tool_ok(PACK)
        return out
