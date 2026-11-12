from dossier.adapters import base
from dossier.adapters import registry


class A1(base.Adapter):
    name = "a1"
    languages = ("Python",)


class TestDetect:
    def test_matching_language_gives_an_instance(self):
        got = registry.detect(["Python"], (A1,))

        assert [type(g) for g in got] == [A1]

    def test_other_language_gives_nothing(self):
        assert registry.detect(["Shell"], (A1,)) == []


class Wild(base.Adapter):
    name = "wild"
    languages = ("*",)


class TestDetectWildcard:
    def test_wildcard_adapter_matches_any_language(self):
        got = registry.detect(["Shell"], (Wild,))

        assert [type(g) for g in got] == [Wild]

    def test_wildcard_adapter_matches_no_languages(self):
        got = registry.detect([], (Wild,))

        assert [type(g) for g in got] == [Wild]
