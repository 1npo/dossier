import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
# scripts/bump_version.py is a maintainer tool; C11 moves it to tools/, outside this scan.
ALLOWED = {"src/dossier/resources.py", "scripts/dossier.py", "scripts/check_page.py", "scripts/bump_version.py"}
FILE_NAME = re.compile(r"(?<![\w.])__file__\b")
MODULE_FILE = re.compile(r"\bmodule\.__file__\b")


def sources():
    found = list((ROOT / "src" / "dossier").rglob("*.py")) + list((ROOT / "scripts").glob("*.py"))
    return sorted(p for p in found if p.relative_to(ROOT).as_posix() not in ALLOWED)


class TestNoFilePaths:
    def test_only_the_resources_module_and_the_launchers_use_the_file_name(self):
        offenders = []
        for path in sources():
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if FILE_NAME.search(line) and not MODULE_FILE.search(line):
                    offenders.append(f"{path.relative_to(ROOT).as_posix()}:{n}")

        assert offenders == []

    def test_the_module_attribute_is_used_only_by_the_gatherer_reader(self):
        users = [p.relative_to(ROOT).as_posix() for p in sources() if MODULE_FILE.search(p.read_text(encoding="utf-8"))]

        assert users == ["src/dossier/render/page.py"]
