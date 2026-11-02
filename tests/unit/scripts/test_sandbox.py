from pathlib import Path

import pytest

import config
import sandbox

FORBIDDEN = {"SSH_AUTH_SOCK": "a", "GIT_AUTHOR_NAME": "b", "AWS_SECRET_ACCESS_KEY": "c", "GITHUB_TOKEN": "d",
             "DATABASE_URL": "e", "MY_SECRET": "f"}


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("DOSSIER_CONFIG", str(tmp_path / "cfg.json"))


@pytest.fixture
def area(tmp_path):
    return tmp_path / "cache" / "repo"


def env_for(area, **kw):
    parent = {"PATH": "/usr/bin", "HTTPS_PROXY": "http://proxy.invalid:3128", **FORBIDDEN, **kw.pop("parent", {})}
    return sandbox.build_env(area, parent=parent, **kw)


class TestBuildEnv:
    def test_forbidden_names_are_absent(self, area):
        assert not FORBIDDEN.keys() & env_for(area).keys()

    def test_only_allowed_names_are_present(self, area):
        assert set(env_for(area)) <= sandbox.ALLOWED_NAMES

    def test_proxy_passes_through(self, area):
        assert env_for(area)["HTTPS_PROXY"] == "http://proxy.invalid:3128"

    def test_home_and_xdg_are_under_the_area(self, area):
        env = env_for(area)

        assert all(Path(env[k]).is_relative_to(area) for k in ("HOME", "TMPDIR", "XDG_CACHE_HOME", "XDG_CONFIG_HOME"))

    def test_restricted_caches_are_under_the_area(self, area):
        env = env_for(area)

        for k in ("UV_CACHE_DIR", "npm_config_cache", "NUGET_PACKAGES", "DOTNET_CLI_HOME", "PIP_CACHE_DIR"):
            assert Path(env[k]).is_relative_to(area / "cache")

    def test_tool_profile_shares_the_uv_cache(self, area):
        env = env_for(area, profile="tool")

        assert Path(env["UV_CACHE_DIR"]).is_relative_to(area.parent / ".dossier-tools")

    def test_tool_profile_shares_the_npm_cache(self, area):
        env = env_for(area, profile="tool")

        assert Path(env["npm_config_cache"]) == area.parent / ".dossier-tools" / "npm"

    def test_registry_name_passes_only_when_listed(self, area):
        config.update(registry_auth={"python": ["MY_INDEX_TOKEN"]})
        parent = {"MY_INDEX_TOKEN": "tok"}

        listed = env_for(area, ecosystem="python", parent=parent)
        unlisted = env_for(area, ecosystem="npm", parent=parent)

        assert listed["MY_INDEX_TOKEN"] == "tok" and "MY_INDEX_TOKEN" not in unlisted

    def test_registry_file_outside_home_is_refused(self, area):
        config.update(registry_auth={"python": ["~/../../etc/passwd"]})

        with pytest.raises(SystemExit, match="outside your home folder"):
            env_for(area, ecosystem="python")

    def test_registry_npmrc_replaces_the_empty_userconfig(self, area, tmp_path, monkeypatch):
        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        (fake_home / ".npmrc").write_text("//r/:_authToken=x\n")
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        config.update(registry_auth={"npm": ["~/.npmrc"]})

        env = env_for(area, ecosystem="npm")

        assert env["npm_config_userconfig"] == str(area / "home" / ".npmrc")
