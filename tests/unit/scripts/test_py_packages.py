import shutil
from pathlib import Path

import pytest

import py_packages
from conftest import PYFIX, line_of


@pytest.fixture
def fix(tmp_path):
    root = tmp_path / "pyrepo"
    shutil.copytree(PYFIX, root, ignore=shutil.ignore_patterns("__pycache__"))
    return root


def tree_of(root: Path) -> frozenset:
    return frozenset(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def write(root: Path, rel: str, text: str) -> None:
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text)


class TestPackageRoots:
    def test_src_layout_gives_one_root_and_package(self, fix):
        assert py_packages.package_roots(tree_of(fix), fix) == [{"root": "src", "package": "shopcart"}]

    def test_tests_folder_is_not_a_package(self, tmp_path):
        write(tmp_path, "tests/__init__.py", "")
        write(tmp_path, "pkg/__init__.py", "")

        got = py_packages.package_roots(tree_of(tmp_path), tmp_path)

        assert got == [{"root": "", "package": "pkg"}]

    def test_flat_layout_has_an_empty_root(self, tmp_path):
        write(tmp_path, "pkg/__init__.py", "")
        write(tmp_path, "pkg/a.py", "")

        got = py_packages.package_roots(tree_of(tmp_path), tmp_path)

        assert got == [{"root": "", "package": "pkg"}]

    def test_wheel_packages_setting_names_a_root(self, tmp_path):
        write(tmp_path, "pyproject.toml", '[tool.hatch.build.targets.wheel]\npackages = ["lib/thing"]\n')
        write(tmp_path, "lib/thing/__init__.py", "")

        got = py_packages.package_roots(tree_of(tmp_path), tmp_path)

        assert got == [{"root": "lib", "package": "thing"}]

    def test_vendored_package_is_left_out(self, tmp_path):
        write(tmp_path, "vendor/__init__.py", "")
        write(tmp_path, "src/vendor/__init__.py", "")

        assert py_packages.package_roots(tree_of(tmp_path), tmp_path) == []


class TestLooseModules:
    def test_files_outside_packages_are_listed_and_tests_are_not(self, fix):
        tree = tree_of(fix)

        got = py_packages.loose_modules(tree, py_packages.package_roots(tree, fix))

        assert got == []

    def test_script_next_to_a_package_is_loose(self, tmp_path):
        write(tmp_path, "pkg/__init__.py", "")
        write(tmp_path, "tool.py", "")
        tree = tree_of(tmp_path)

        got = py_packages.loose_modules(tree, py_packages.package_roots(tree, tmp_path))

        assert got == ["tool.py"]


class TestConsoleScripts:
    def test_project_script_has_target_and_marker_line(self, fix):
        got = py_packages.console_scripts(fix)

        assert got == [{"name": "shopcart", "target": "shopcart.cli:main", "line": line_of(fix, "pyproject.toml", "ep-script"),
                        "path": "pyproject.toml", "group": "scripts"}]

    def test_setup_cfg_console_scripts_are_read(self, tmp_path):
        write(tmp_path, "setup.cfg", "[options.entry_points]\nconsole_scripts =\n    tool = pkg.cli:run\n")

        got = py_packages.console_scripts(tmp_path)

        assert [(s["name"], s["target"], s["line"]) for s in got] == [("tool", "pkg.cli:run", 3)]

    def test_broken_pyproject_gives_nothing(self, tmp_path):
        write(tmp_path, "pyproject.toml", "[project\n")

        assert py_packages.console_scripts(tmp_path) == []


class TestImportlinterContracts:
    def test_pyproject_contracts_keep_layer_order(self, fix):
        got = py_packages.importlinter_contracts(fix)

        layers = next(c for c in got["contracts"] if c["type"] == "layers")
        assert layers["layers"] == ["shopcart.cli", "shopcart.core"] and got["root_packages"] == ["shopcart"]

    def test_independence_contract_is_listed_with_its_modules(self, fix):
        got = py_packages.importlinter_contracts(fix)

        other = next(c for c in got["contracts"] if c["type"] == "independence")
        assert other["name"] == "apps apart" and other["modules"] == ["shopcart.plugins", "shopcart.store"]

    def test_contract_line_is_the_line_of_its_name(self, fix):
        got = py_packages.importlinter_contracts(fix)

        lines = (fix / "pyproject.toml").read_text().splitlines()
        assert lines[got["contracts"][0]["line"] - 1] == 'name = "cli above core"'

    def test_ini_file_with_multiline_layers(self, tmp_path):
        write(tmp_path, ".importlinter",
              "[importlinter]\nroot_package = app\n\n[importlinter:contract:one]\nname = Layers\ntype = layers\nlayers =\n    app.web\n    app.db\n")

        got = py_packages.importlinter_contracts(tmp_path)

        assert got["path"] == ".importlinter" and got["contracts"][0]["layers"] == ["app.web", "app.db"]

    def test_broken_pyproject_gives_empty_contracts_and_an_error(self, tmp_path):
        write(tmp_path, "pyproject.toml", "[tool\nbroken")

        got = py_packages.importlinter_contracts(tmp_path)

        assert got["contracts"] == [] and "pyproject.toml" in got["error"]

    def test_no_config_gives_empty_without_error(self, tmp_path):
        assert py_packages.importlinter_contracts(tmp_path) == {"path": None, "root_packages": [], "contracts": []}


class TestVultureConfig:
    def test_defaults_when_nothing_is_set(self, fix):
        assert py_packages.vulture_config(fix) == {"ignore_names": [], "ignore_decorators": [], "exclude": [], "min_confidence": 60}

    def test_values_from_pyproject(self, tmp_path):
        write(tmp_path, "pyproject.toml", '[tool.vulture]\nignore_names = ["x"]\nmin_confidence = 80\n')

        got = py_packages.vulture_config(tmp_path)

        assert got["ignore_names"] == ["x"] and got["min_confidence"] == 80


class TestTestConfigs:
    def test_pytest_and_coverage_settings_from_pyproject(self, fix):
        got = py_packages.test_configs(fix, tree_of(fix))

        by_tool = {c["tool"]: c for c in got}
        assert by_tool["pytest"]["settings"] == {"testpaths": ["tests"]} and by_tool["coverage"]["settings"] == {"fail_under": 80}

    def test_tox_and_nox_files_are_listed_when_tracked(self, tmp_path):
        write(tmp_path, "tox.ini", "[tox]\n")
        write(tmp_path, "noxfile.py", "")

        got = py_packages.test_configs(tmp_path, tree_of(tmp_path))

        assert sorted(c["tool"] for c in got) == ["nox", "tox"]
