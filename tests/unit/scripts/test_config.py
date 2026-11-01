import json
from pathlib import Path

import pytest

import config


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("DOSSIER_CONFIG", str(tmp_path / "c.json"))
    monkeypatch.delenv("DOSSIER_HOME", raising=False)
    monkeypatch.delenv("DOSSIER_CACHE", raising=False)


class TestUpdate:
    def test_keeps_unrelated_keys(self):
        config.update(cache_dir="/x")

        config.update(home="/h")

        assert config.load() == {"cache_dir": "/x", "home": "/h"}


class TestHome:
    def test_env_wins_over_file(self, monkeypatch):
        config.update(home="/from-file")
        monkeypatch.setenv("DOSSIER_HOME", "/from-env")

        assert config.home() == Path("/from-env")

    def test_unset_is_none(self):
        assert config.home() is None


class TestCacheRoot:
    def test_default_ends_with_local_cache_dossier(self):
        assert config.cache_root().parts[-3:] == (".local", "cache", "dossier")

    def test_env_wins_over_file(self, monkeypatch):
        config.update(cache_dir="/file")
        monkeypatch.setenv("DOSSIER_CACHE", "/env")

        assert config.cache_root() == Path("/env")


class TestTimeouts:
    def test_defaults_and_override(self):
        config.update(timeouts={"restore": 5})

        assert config.timeouts() == {"restore": 5, "extract": 1800, "tool": 600}

    def test_bad_value_exits_with_message(self):
        config.update(timeouts={"restore": -1})

        with pytest.raises(SystemExit, match="positive number"):
            config.timeouts()


class TestRegistryAuth:
    def test_non_list_value_exits(self):
        config.update(registry_auth={"python": "TOKEN"})

        with pytest.raises(SystemExit, match="list of strings"):
            config.registry_auth()

    def test_valid_value_is_returned(self):
        config.update(registry_auth={"python": ["A"]})

        assert config.registry_auth() == {"python": ["A"]}


class TestLoad:
    def test_invalid_json_exits_naming_the_path(self, tmp_path):
        (tmp_path / "c.json").write_text("{nope")

        with pytest.raises(SystemExit, match="c.json"):
            config.load()
