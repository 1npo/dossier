"""The skill runs on Python 3.11+, so no file in scripts/, src/ or tools/ may use syntax that only 3.12
accepts (a backslash or reused quote inside an f-string expression)."""
import pathlib
import shutil
import subprocess

import pytest
from paths import SKILL_ROOT as ROOT

CHECK = (
    "import ast,sys\n"
    "bad=0\n"
    "for f in sys.argv[1:]:\n"
    "    try: ast.parse(open(f,encoding='utf-8').read(),f)\n"
    "    except SyntaxError as e: print(f,e.lineno,e.msg); bad=1\n"
    "sys.exit(bad)\n"
)


def test_scripts_parse_on_python_311():
    uv = shutil.which("uv")
    if not uv:
        pytest.skip("uv not available")
    files = [str(p) for folder in ("scripts", "src", "tools") for p in sorted((ROOT / folder).rglob("*.py"))]
    r = subprocess.run(
        [uv, "run", "--python", "3.11", "--no-project", "python", "-I", "-c", CHECK, *files],
        capture_output=True, text=True,
    )
    if r.returncode != 0 and "No interpreter found" in r.stderr:
        pytest.skip("Python 3.11 not available")
    assert r.returncode == 0, r.stdout + r.stderr
