import os
import shlex
import subprocess

import pytest

import candidates
import toolcheck

TOOLS = toolcheck.load_tools()


def fake_bin(tmp_path, **versions):
    d = tmp_path / "bin"
    d.mkdir(exist_ok=True)
    for name, out in versions.items():
        f = d / name
        f.write_text("#!/bin/sh\nprintf '%s\\n' " + shlex.quote(out) + "\n")
        f.chmod(0o755)
    return str(d)


ALL = dict(git="git version 2.47.3", uv="uv 0.11.19 (abc)", node="v22.14.0", npm="9.2.0", dotnet="8.0.100 [/x]\n9.0.200 [/x]")


def git_in(cwd, *args):
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, env=env)


class TestPreflight:
    def test_everything_present_misses_nothing(self, tmp_path):
        path = fake_bin(tmp_path, **ALL)

        report = toolcheck.preflight(["Python"], path=path)

        assert report["missing"] == []

    def test_missing_node_also_blocks_scip_python(self, tmp_path):
        versions = {k: v for k, v in ALL.items() if k != "node"}
        path = fake_bin(tmp_path, **versions)

        report = toolcheck.preflight(["Python"], path=path)

        assert "node" in report["missing"] and "scip-python" in report["missing"]
        scip = next(s for s in report["self_installing"] if s["id"] == "scip-python")
        assert scip["needs"] == ["node"]

    def test_old_node_is_too_old_for_typescript(self, tmp_path):
        path = fake_bin(tmp_path, **{**ALL, "node": "v20.19.2"})

        report = toolcheck.preflight(["TypeScript"], path=path)

        node = next(h for h in report["host"] if h["id"] == "node")
        assert (node["status"], node["needs"], node["for"]) == ("old", "22.13.0", ["TypeScript"])

    def test_old_node_is_fine_for_python(self, tmp_path):
        path = fake_bin(tmp_path, **{**ALL, "node": "v20.19.2"})

        report = toolcheck.preflight(["Python"], path=path)

        assert next(h for h in report["host"] if h["id"] == "node")["status"] == "ok"

    def test_dotnet_picks_the_highest_sdk(self, tmp_path):
        path = fake_bin(tmp_path, **ALL)

        report = toolcheck.preflight(["C#"], path=path)

        assert next(h for h in report["host"] if h["id"] == "dotnet")["version"] == "9.0.200"

    def test_all_scopes_checks_every_host_tool(self, tmp_path):
        report = toolcheck.preflight([], path=fake_bin(tmp_path, **ALL), all_scopes=True)

        assert {h["id"] for h in report["host"]} == {"git", "gh", "uv", "node", "npm", "dotnet"}


class TestOptionalTools:
    def test_missing_gh_is_not_in_missing(self, tmp_path):
        report = toolcheck.preflight(["Python"], path=fake_bin(tmp_path, **ALL))

        gh = next(h for h in report["host"] if h["id"] == "gh")
        assert gh["status"] == "missing" and gh["optional"] is True
        assert "gh" not in report["missing"] and report["missing"] == []

    def test_installed_gh_is_listed_with_its_version(self, tmp_path):
        report = toolcheck.preflight(["Python"], path=fake_bin(tmp_path, gh="gh version 2.63.0 (2025-01-01)", **ALL))

        assert next(h for h in report["host"] if h["id"] == "gh")["version"] == "2.63.0"

    def test_format_text_lists_gh_under_optional_and_still_says_nothing_is_missing(self, tmp_path):
        text = toolcheck.format_text(toolcheck.preflight(["Python"], path=fake_bin(tmp_path, **ALL)))

        assert "Optional (a build works without them):" in text and "not found gh" in text
        assert "MISSING  gh" not in text and text.endswith("Nothing is missing.")


class TestTier:
    def test_python_is_a(self):
        assert toolcheck.tier_of("Python", TOOLS) == "A"

    def test_shell_is_b(self):
        assert toolcheck.tier_of("Shell", TOOLS) == "B"


class TestParseVersion:
    def test_dotted_integers(self):
        assert toolcheck.parse_version("22.1.0") == (22, 1, 0)


class TestLanguagesAt:
    def test_fixture_without_extensions_has_none(self, git_repo):
        sha = subprocess.run(["git", "-C", str(git_repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()

        assert toolcheck.languages_at(str(git_repo), sha) == []

    def test_orders_by_file_count_then_name(self, tmp_path):
        git_in(tmp_path, "init", "-b", "main")
        for n in ("a.py", "b.sh", "README.md"):
            (tmp_path / n).write_text("x\n")
        git_in(tmp_path, "add", "-A")
        git_in(tmp_path, "-c", "user.name=t", "-c", "user.email=t@x", "commit", "-m", "m")
        sha = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()

        assert toolcheck.languages_at(str(tmp_path), sha) == ["Python", "Shell"]


class TestToolsFile:
    def test_tool_entries_have_required_keys(self):
        for t in TOOLS["tools"]:
            assert {"id", "scope", "via", "version", "source"} <= set(t)
            assert t["version"] is not None or t.get("open")

    def test_restore_entries_have_required_keys(self):
        for r in TOOLS["restore"]:
            assert {"ecosystem", "lockfile", "command", "enabled"} <= set(r)

    def test_counts(self):
        assert (len(TOOLS["host"]), len(TOOLS["tools"]), len(TOOLS["restore"])) == (6, 15, 3)


class TestFormatText:
    def test_missing_tool_lists_install_and_summary(self, tmp_path):
        versions = {k: v for k, v in ALL.items() if k not in ("node", "npm")}
        report = toolcheck.preflight(["Python"], path=fake_bin(tmp_path, **versions))

        text = toolcheck.format_text(report)

        assert "MISSING  node" in text and "Install:" in text
        assert "2 tools are missing." in text
        assert "cannot install: needs node, npm" in text

    def test_nothing_missing(self, tmp_path):
        report = toolcheck.preflight(["Python"], path=fake_bin(tmp_path, **ALL))

        assert toolcheck.format_text(report).endswith("Nothing is missing.")


class TestToolCards:
    def test_every_card_named_in_tools_json_exists_in_the_schemas(self):
        known = candidates.card_titles()

        unknown = [(t["id"], c) for t in TOOLS["tools"] for c in t["cards"] if c not in known]

        assert unknown == []

    def test_every_tool_declares_its_cards(self):
        assert all(isinstance(t.get("cards"), list) for t in TOOLS["tools"])


class TestDoctorTextForLockedTools:
    def report(self, **kw):
        return {"languages": [], "host": [], "self_installing": [{"id": "scip-python", "version": "0.6.6", "via": "npx", "locked": True, "status": "first-use", "needs": []},
                                                                   {"id": "other", "version": "1", "via": "uv", "locked": False, "status": "first-use", "needs": []}],
                "missing": [], **kw}

    def test_a_tool_installed_from_a_lockfile_does_not_say_npx(self):
        text = toolcheck.format_text(self.report())

        assert "scip-python 0.6.6 from a lockfile with npm" in text and "via npx" not in text

    def test_other_tools_keep_their_install_route(self):
        assert "other 1 via uv" in toolcheck.format_text(self.report())
