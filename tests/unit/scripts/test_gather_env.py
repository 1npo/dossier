import os
import subprocess

import gather


def make_repo(tmp_path, source):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text(source)
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull, "GIT_AUTHOR_NAME": "A", "GIT_AUTHOR_EMAIL": "a@x.io",
           "GIT_COMMITTER_NAME": "A", "GIT_COMMITTER_EMAIL": "a@x.io"}
    for args in (["init", "-b", "main"], ["add", "-A"], ["commit", "-m", "x"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)
    return repo


def reads(n):
    return "import os\n" + "".join(f'os.environ.get("APP_VAR_{i:03d}")\n' for i in range(n))


class TestEnvVars:
    def test_seventy_reads_in_one_file_are_all_found(self, tmp_path):
        facts, _ = gather.collect(str(make_repo(tmp_path, reads(70))))

        assert len(facts["env_vars"]) == 70

    def test_more_than_three_hundred_names_are_all_kept(self, tmp_path):
        facts, _ = gather.collect(str(make_repo(tmp_path, reads(350))))

        assert len(facts["env_vars"]) == 350
