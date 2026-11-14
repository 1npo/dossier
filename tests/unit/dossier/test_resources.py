import os
import subprocess
import sys
from pathlib import Path

from dossier import resources

SRC = Path(resources.skill_root()) / "src"


def test_ensure_utf8_lets_a_piped_cp1252_console_print_an_arrow_and_a_non_bmp_character():
    code = "from dossier import resources; resources.ensure_utf8(); print('a \u2192 b \U0001f600')"
    env = {**os.environ, "PYTHONPATH": str(SRC), "PYTHONIOENCODING": "cp1252"}
    env.pop("PYTHONUTF8", None)

    r = subprocess.run([sys.executable, "-c", code], capture_output=True, env=env)

    assert r.returncode == 0
    assert r.stdout.decode("utf-8").strip() == "a \u2192 b \U0001f600"
