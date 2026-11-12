from types import SimpleNamespace

from dossier.adapters import base as adapters
from dossier.adapters import tier_b


class FakeTS:
    def __init__(self, matches=None, fail=None):
        self.matches, self.fail, self.calls = matches or {}, fail, []

    def query(self, language, paths, query):
        self.calls.append((language, list(paths), query))
        if self.fail == language:
            raise RuntimeError("grammar missing\nmore")
        return self.matches.get(language, [])


def m(path, capture, text, line):
    return {"path": path, "capture": capture, "start_line": line, "start_col": 0, "end_line": line, "end_col": 1, "text": text}


class TestFiles:
    def test_only_files_of_the_language_that_are_not_noise(self):
        paths = ["a.sh", "b/c.bash", "x.fish", "vendor/v.sh", "main.rs", "z.zsh", "readme.md"]

        assert tier_b.files_of("Shell", paths) == ["a.sh", "b/c.bash", "z.zsh"]

    def test_ruby_rake_and_gemspec_count(self):
        assert tier_b.files_of("Ruby", ["lib/a.rb", "t.rake", "x.gemspec", "a.py"]) == ["lib/a.rb", "t.rake", "x.gemspec"]


class TestSymbols:
    def test_a_capture_becomes_a_decl_with_path_line_kind_and_language(self):
        ts = FakeTS({"go": [m("s.go", "type", "Server", 4), m("s.go", "function", "New", 15)]})

        got = tier_b.symbols(ts, "Go", ["s.go"])

        assert got == [{"kind": "decl", "path": "s.go", "line": 4, "name": "Server", "symbol_kind": "type", "language": "Go", "via": "tree-sitter"},
                       {"kind": "decl", "path": "s.go", "line": 15, "name": "New", "symbol_kind": "function", "language": "Go", "via": "tree-sitter"}]

    def test_no_files_means_no_call(self):
        ts = FakeTS()

        assert tier_b.symbols(ts, "Rust", []) == [] and ts.calls == []

    def test_the_query_uses_the_grammar_name_not_the_dossier_name(self):
        ts = FakeTS()
        tier_b.symbols(ts, "Shell", ["a.sh"])

        assert ts.calls[0][0] == "bash"

    def test_every_query_is_anchored_at_the_root_so_only_top_level_definitions_match(self):
        assert all(q.startswith(("(program", "(source_file")) for _, _, q in tier_b.LANGUAGES.values())


def ctx(tree, ts):
    return SimpleNamespace(tree=frozenset(tree), treesitter=ts, tool_status={})


class TestAdapter:
    def test_it_is_registered_and_runs_only_for_its_languages(self):
        assert tier_b.TierBAdapter in adapters._registered()
        assert [a.name for a in adapters.detect(["Python"], (tier_b.TierBAdapter,))] == []
        assert [a.name for a in adapters.detect(["Shell"], (tier_b.TierBAdapter,))] == ["tier-b"]

    def test_symbols_from_every_language_present_and_tool_ok(self):
        ts = FakeTS({"bash": [m("a.sh", "function", "deploy", 3)], "rust": [m("l.rs", "struct", "Config", 2)]})
        c = ctx(["a.sh", "l.rs", "x.py"], ts)

        out = tier_b.TierBAdapter().extract(c)

        assert [(s["language"], s["name"]) for s in out["symbols"]] == [("Shell", "deploy"), ("Rust", "Config")]
        assert c.tool_status[tier_b.PACK] == {"status": "ok", "reason": None} and [call[0] for call in ts.calls] == ["bash", "rust"]

    def test_a_failing_grammar_is_named_and_the_others_still_run(self):
        ts = FakeTS({"rust": [m("l.rs", "struct", "Config", 2)]}, fail="bash")
        c = ctx(["a.sh", "l.rs"], ts)

        out = tier_b.TierBAdapter().extract(c)

        assert [s["name"] for s in out["symbols"]] == ["Config"]
        assert c.tool_status[tier_b.PACK] == {"status": "failed", "reason": "Shell: grammar missing"}
