import subprocess
from types import SimpleNamespace

import repo_adapter
from test_repo_adapter import FakeSemgrep


class TestShellVariables:
    def got(self, text, makefile=False):
        return [(i["line"], i["detail"], i["rule"], i["snippet"]) for i in repo_adapter.shell_variables("x", text, makefile)]

    def test_makefile_default_assignment_is_an_input(self):
        text = "PREFIX ?= /usr/local\nCC := gcc\nall:\n\t$(CC) -o app\n"

        assert self.got(text, makefile=True) == [(1, "PREFIX", "repo.makefile-var", "PREFIX ?=")]

    def test_makefile_export_forms(self):
        text = "export API_URL\nexport A B\nexport FIXED = 1\nexport OPT ?= 2\n"

        assert [(g[0], g[1]) for g in self.got(text, makefile=True)] == [(1, "API_URL"), (2, "A"), (2, "B"), (4, "OPT")]

    def test_a_recipe_line_is_not_an_assignment_but_its_shell_default_counts(self):
        text = "run:\n\tX ?= 1\n\tgo run -port $${PORT:-8080}\n"

        assert [(g[0], g[1]) for g in self.got(text, makefile=True)] == [(3, "PORT")]

    def test_shell_default_forms_are_inputs(self):
        text = "a=${ONE:-1}\nb=${TWO-2}\nc=${THREE:=3}\nd=${FOUR=4}\ne=${FIVE:?needed}\nf=${SIX:+yes}\n"

        assert [g[1] for g in self.got(text)] == ["ONE", "TWO", "THREE", "FOUR"]

    def test_plain_uses_and_assignments_add_nothing(self):
        text = 'echo "$HOME" ${USER} $PATH\nNAME=x\nexport TOKEN=abc\ncd "$1" "${2}" "${#NAME}"\n'

        assert self.got(text) == []

    def test_bare_export_in_a_script_is_an_input(self):
        assert [(g[1], g[3]) for g in self.got("#!/bin/sh\nexport DB_URL\n")] == [("DB_URL", "export DB_URL")]

    def test_a_name_is_listed_once_at_its_first_line(self):
        text = "export A\nx=${A:-1}\ny=${B:-2}\nz=${B:-3}\n"

        assert [(g[0], g[1]) for g in self.got(text)] == [(1, "A"), (3, "B")]

    def test_comments_are_skipped_and_no_value_is_stored(self):
        text = "# export HIDDEN\nTOKEN=${TOKEN:-hunter2}\n"

        items = repo_adapter.shell_variables("x", text)

        assert [i["detail"] for i in items] == ["TOKEN"]
        assert "hunter2" not in str(items)


class TestShellVariablesInTheAdapter:
    def test_a_makefile_and_scripts_give_rows_and_a_plain_home_use_gives_none(self, tmp_path):
        repo = tmp_path / "r"
        (repo / "bin").mkdir(parents=True)
        (repo / "Makefile").write_text("PREFIX ?= /usr/local\nall:\n\techo $(HOME)\n")
        (repo / "bin" / "run.sh").write_text('#!/bin/bash\necho "$HOME"\nport=${PORT:-80}\n')
        (repo / "bin" / "plain.sh").write_text('#!/bin/bash\necho "$HOME" ${USER}\n')
        (repo / "bin" / "run.sh").chmod(0o755)

        def git(*a):
            return subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True).stdout

        git("init", "-b", "main")
        git("add", "-A")
        git("-c", "user.name=t", "-c", "user.email=t@x.io", "commit", "-m", "x")
        ctx = SimpleNamespace(checkout=repo, sha=git("rev-parse", "HEAD").strip(), tree=frozenset(git("ls-files").split()), files=[],
                              semgrep=FakeSemgrep(), tool_status={})

        out = repo_adapter.RepoAdapter().extract(ctx)

        assert [(i["path"], i["detail"]) for i in out["io_candidates"]] == [("Makefile", "PREFIX"), ("bin/run.sh", "PORT")]
