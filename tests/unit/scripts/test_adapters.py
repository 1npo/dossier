import json

import pytest

import adapters
import js_adapter
import py_adapter
import repo_adapter


class A1(adapters.Adapter):
    name = "a1"
    languages = ("Python",)


TREE = frozenset({"app.py", "src/a.py"})


def filt(outputs, globs=()):
    return adapters.filter_paths(outputs, TREE, "/checkout", globs)


class TestFilterPaths:
    def test_tracked_path_is_kept(self):
        kept, stats = filt({"graph": [{"path": "app.py"}]})

        assert kept["graph"] == [{"path": "app.py"}] and stats["paths_dropped"] == 0

    def test_venv_path_is_dropped_as_expected(self):
        kept, stats = filt({"graph": [{"path": ".venv/lib/x.py"}]})

        assert kept["graph"] == [] and stats["dropped_expected"] == 1

    def test_absolute_path_outside_checkout_is_dropped_as_outside(self):
        kept, stats = filt({"graph": [{"path": "/usr/lib/x.py"}]})

        assert kept["graph"] == [] and stats["dropped_outside"] == 1

    def test_absolute_path_inside_checkout_becomes_relative(self):
        kept, _ = filt({"graph": [{"path": "/checkout/app.py"}]})

        assert kept["graph"] == [{"path": "app.py"}]

    def test_adapter_glob_makes_a_drop_expected(self):
        _, stats = filt({"graph": [{"path": "build/gen.py"}]}, globs=("build/**",))

        assert (stats["dropped_expected"], stats["dropped_unexpected"]) == (1, 0)

    def test_unknown_path_is_unexpected_and_listed(self):
        _, stats = filt({"graph": [{"path": "weird/new.py"}]})

        assert stats["dropped_unexpected"] == 1 and stats["unexpected"] == ["weird/new.py"]

    def test_paths_list_loses_only_dropped_entries(self):
        kept, _ = filt({"graph": [{"path": "app.py", "paths": ["src/a.py", "ghost.py"]}]})

        assert kept["graph"][0]["paths"] == ["src/a.py"]

    def test_item_without_path_raises(self):
        with pytest.raises(ValueError):
            filt({"graph": [{"kind": "x"}]})


class TestDetect:
    def test_matching_language_gives_an_instance(self):
        got = adapters.detect(["Python"], (A1,))

        assert [type(g) for g in got] == [A1]

    def test_other_language_gives_nothing(self):
        assert adapters.detect(["Shell"], (A1,)) == []


class Wild(adapters.Adapter):
    name = "wild"
    languages = ("*",)


class TestDetectWildcard:
    def test_wildcard_adapter_matches_any_language(self):
        got = adapters.detect(["Shell"], (Wild,))

        assert [type(g) for g in got] == [Wild]

    def test_wildcard_adapter_matches_no_languages(self):
        got = adapters.detect([], (Wild,))

        assert [type(g) for g in got] == [Wild]


class WithRules(adapters.Adapter):
    name = "with-rules"
    tools = ("semgrep",)


class TestKey:
    def test_a_change_to_a_rule_file_changes_the_key(self, tmp_path):
        (tmp_path / "a.yml").write_text("rules: []\n")
        adapter = WithRules()
        adapter.rules = (tmp_path,)
        before = adapters._key(adapter, "sha", {})

        (tmp_path / "a.yml").write_text("rules: [x]\n")
        after = adapters._key(adapter, "sha", {})

        assert before != after

    def test_the_same_rule_files_give_the_same_key(self, tmp_path):
        (tmp_path / "a.yml").write_text("rules: []\n")
        adapter = WithRules()
        adapter.rules = (tmp_path,)

        assert adapters._key(adapter, "sha", {}) == adapters._key(adapter, "sha", {})

    def test_a_build_stored_without_a_rules_hash_is_not_reusable(self, tmp_path):
        (tmp_path / "a.yml").write_text("rules: []\n")
        adapter = WithRules()
        adapter.rules = (tmp_path,)
        key = adapters._key(adapter, "sha", {})
        old = {k: v for k, v in key.items() if k != "rules"}
        (tmp_path / "extract").mkdir()
        (tmp_path / "extract" / "entry_points.json").write_text('{"adapters": {"with-rules": %s}}' % json.dumps(old))

        assert not adapters._reusable(tmp_path, adapter, key)

    def test_shipped_adapters_name_their_rule_folders(self):
        assert [a.rules for a in (js_adapter.JsAdapter, py_adapter.PythonAdapter, repo_adapter.RepoAdapter)] == [
            (js_adapter.RULES,), (py_adapter.RULES,), (repo_adapter.RULES_ALL,)]
