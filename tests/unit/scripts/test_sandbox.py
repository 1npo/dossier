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


class TestGithubProfile:
    def test_gets_the_config_folder_and_the_no_prompt_names(self, area):
        env = env_for(area, profile="github", parent={"HOME": "/home/u"})

        assert env["GH_CONFIG_DIR"] == "/home/u/.config/gh"
        assert env["GH_PROMPT_DISABLED"] == "1" and env["GH_NO_UPDATE_NOTIFIER"] == "1"
        assert set(env) <= sandbox.ALLOWED_NAMES

    def test_parent_config_dir_wins_then_xdg(self, area):
        assert env_for(area, profile="github", parent={"GH_CONFIG_DIR": "/x/gh", "HOME": "/h"})["GH_CONFIG_DIR"] == "/x/gh"
        assert env_for(area, profile="github", parent={"XDG_CONFIG_HOME": "/xdg", "HOME": "/h"})["GH_CONFIG_DIR"] == "/xdg/gh"

    def test_no_other_profile_gets_the_names(self, area):
        for profile in ("restricted", "tool"):
            env = env_for(area, profile=profile, parent={"GH_CONFIG_DIR": "/x"})

            assert not {k for k in env if k.startswith("GH_")}

    def test_no_variable_name_holds_a_token(self, area):
        env = env_for(area, profile="github", parent={"GH_TOKEN": "t", "GITHUB_TOKEN": "t", "HOME": "/h"})

        assert not [k for k in env if "TOKEN" in k.upper()]
        assert not [n for n in sandbox.ALLOWED_NAMES if "TOKEN" in n.upper()]


class TestHostPath:
    def test_a_version_manager_folder_comes_before_the_system_folders(self, tmp_path):
        """git sits in /usr/bin, and the tools are looked up in order, so /usr/bin must not hide a newer node."""
        fnm = tmp_path / "fnm" / "bin"
        fnm.mkdir(parents=True)
        node = fnm / "node"
        node.write_text("#!/bin/sh\n")
        node.chmod(0o755)

        dirs = sandbox._host_path({"PATH": f"{fnm}:/usr/bin"}).split(":")

        assert dirs.index(str(fnm)) < dirs.index("/usr/bin")

    def test_system_folders_are_always_present(self):
        dirs = sandbox._host_path({"PATH": "/nowhere"}).split(":")

        assert dirs == list(sandbox.SAFE_PATH)


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
