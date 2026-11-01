import pytest

import adapters


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
