import os
import subprocess
import sys
from pathlib import Path

from dossier import resources

SRC = Path(resources.skill_root()) / "src"


def test_python_dash_m_dossier_prints_the_version():
    env = {**os.environ, "PYTHONPATH": str(SRC)}

    r = subprocess.run([sys.executable, "-m", "dossier", "version"], capture_output=True, text=True, env=env, cwd=SRC)

    assert r.returncode == 0
    assert r.stdout.strip() == f"dossier {resources.version()}"
