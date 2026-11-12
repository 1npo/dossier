import os
import subprocess

from dossier.facts import gather
from repos import make_repo


def reads(n):
    return "import os\n" + "".join(f'os.environ.get("APP_VAR_{i:03d}")\n' for i in range(n))


class TestEnvVars:
    def test_seventy_reads_in_one_file_are_all_found(self, tmp_path):
        facts, _ = gather.collect(str(make_repo(tmp_path, reads(70))))

        assert len(facts["env_vars"]) == 70

    def test_more_than_three_hundred_names_are_all_kept(self, tmp_path):
        facts, _ = gather.collect(str(make_repo(tmp_path, reads(350))))

        assert len(facts["env_vars"]) == 350
