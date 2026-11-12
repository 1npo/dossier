import ast
import re

from paths import SKILL_ROOT

TESTS = SKILL_ROOT / "tests"
SRC = SKILL_ROOT / "src" / "dossier"
STANDALONE = {"layout_probe.py", "diagram_text.py", "table_fit.py", "m3_page.py", "m4_page.py", "m5_page.py", "m6_page.py"}
SYS_PATH = re.compile(r"\bsys\.path\b")


def all_python_files():
    return sorted(p for p in TESTS.rglob("*.py") if "__pycache__" not in p.parts and "fixtures" not in p.relative_to(TESTS).parts)


class TestTreeMirrorsPackage:
    def test_every_unit_test_sits_in_a_folder_that_exists_in_the_package(self):
        unit = TESTS / "unit" / "dossier"

        orphans = [p.relative_to(TESTS).as_posix() for p in unit.rglob("test_*.py")
                   if not (SRC / p.parent.relative_to(unit)).is_dir()]

        assert orphans == []

    def test_every_integration_test_sits_in_a_folder_that_exists_in_the_package(self):
        integration = TESTS / "integration" / "dossier"

        orphans = [p.relative_to(TESTS).as_posix() for p in integration.rglob("test_*.py")
                   if not (SRC / p.parent.relative_to(integration)).is_dir()]

        assert orphans == []


class TestNoTestImportsAnotherTest:
    def test_no_module_imports_a_test_module(self):
        names = {p.stem for p in all_python_files() if p.name.startswith("test_")}
        offenders = []
        for path in all_python_files():
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    modules = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                    modules = [node.module]
                else:
                    continue
                offenders += [f"{path.relative_to(TESTS).as_posix()}: {m}" for m in modules if m.split(".")[0] in names]

        assert offenders == []


class TestSysPath:
    def test_only_the_standalone_helpers_change_the_import_path(self):
        users = [p for p in all_python_files() if SYS_PATH.search(p.read_text(encoding="utf-8"))]

        offenders = [p.relative_to(TESTS).as_posix() for p in users
                     if p.parent != TESTS / "support" or p.name not in STANDALONE]

        assert offenders == []
