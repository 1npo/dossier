import py_api
import py_packages
import py_project
from conftest import PYLIB, line_of

TREE = frozenset(p.relative_to(PYLIB).as_posix() for p in PYLIB.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def read(path):
    try:
        return (PYLIB / path).read_text(encoding="utf-8")
    except OSError:
        return None


def project(name):
    return next(p for p in py_project.projects(TREE, read) if p["dir"] == name)


def roots_of(name):
    view = PYLIB / name
    vtree = frozenset(p[len(name) + 1:] for p in TREE if p.startswith(name + "/"))
    return [{"root": f"{name}/{r['root']}".rstrip("/"), "package": r["package"]} for r in py_packages.package_roots(vtree, view)]


def api(name, tree=TREE, rd=read):
    return py_api.items(project(name), roots_of(name), tree, rd)


def rows(symbols, subpath):
    return {s["name"]: s for s in symbols if s["subpath"] == subpath and not s["symbol_kind"].startswith("entry point")}


class TestIsLibrary:
    def test_a_packable_project_with_py_typed_is_a_library(self):
        assert py_api.is_library(project("typedlib"), read, TREE) is True

    def test_a_packable_project_without_scripts_is_a_library(self):
        assert py_api.is_library(project("flatlib"), read, TREE) is True

    def test_a_packable_project_with_scripts_and_no_py_typed_is_an_application(self):
        assert py_api.is_library(project("app"), read, TREE) is False

    def test_a_project_that_is_not_packable_is_not_a_library(self):
        tree = frozenset({"x/requirements.txt", "x/run.py"})

        assert py_api.is_library(py_project.projects(tree)[1], lambda p: "", tree) is False

    def test_scripts_in_setup_cfg_make_an_application(self):
        files = {"x/setup.cfg": "[metadata]\nname = x\n[options.entry_points]\nconsole_scripts =\n    x = x.main:main\n", "x/x/__init__.py": ""}
        tree = frozenset(files)

        assert py_api.is_library(py_project.projects(tree)[1], files.get, tree) is False

    def test_scripts_in_poetry_make_an_application(self):
        files = {"x/pyproject.toml": '[tool.poetry]\nname = "x"\n[tool.poetry.scripts]\nx = "x:main"\n[build-system]\nrequires = []\n',
                 "x/x/__init__.py": ""}
        tree = frozenset(files)

        assert py_api.is_library(py_project.projects(tree)[1], files.get, tree) is False


class TestDistributionName:
    def test_project_table_name_wins(self):
        assert py_api.distribution_name(project("typedlib"), read) == "typedlib"

    def test_poetry_name_is_used_without_a_project_table(self):
        files = {"p/pyproject.toml": '[tool.poetry]\nname = "poet"\n', "p/a.py": ""}

        assert py_api.distribution_name(py_project.projects(frozenset(files))[1], files.get) == "poet"

    def test_setup_cfg_name_is_used(self):
        files = {"p/setup.cfg": "[metadata]\nname = fromcfg\n", "p/a.py": ""}

        assert py_api.distribution_name(py_project.projects(frozenset(files))[1], files.get) == "fromcfg"

    def test_setup_py_name_is_read_with_ast(self):
        files = {"p/setup.py": "from setuptools import setup\nsetup(name='frompy')\n", "p/a.py": ""}

        assert py_api.distribution_name(py_project.projects(frozenset(files))[1], files.get) == "frompy"

    def test_the_folder_name_is_the_last_resort(self):
        files = {"folder/requirements.txt": "", "folder/a.py": ""}

        assert py_api.distribution_name(py_project.projects(frozenset(files))[1], files.get) == "folder"


class TestTypedlib:
    def test_top_level_names_come_from_all_and_are_followed_to_the_definition(self):
        symbols, _ = api("typedlib")

        top = rows(symbols, "typedlib")
        assert set(top) == {"parse", "Config", "VERSION"}
        assert top["parse"]["path"] == "typedlib/src/typedlib/_core.py"
        assert top["parse"]["line"] == line_of(PYLIB, "typedlib/src/typedlib/_core.py", "api-parse") and top["Config"]["line"] == line_of(PYLIB, "typedlib/src/typedlib/_core.py", "api-config")
        assert top["VERSION"]["path"] == "typedlib/src/typedlib/__init__.py"
        assert {s["audience"] for s in top.values()} == {"listed in __all__, typed"}

    def test_kinds_are_function_class_and_variable(self):
        symbols, _ = api("typedlib")

        top = rows(symbols, "typedlib")
        assert (top["parse"]["symbol_kind"], top["Config"]["symbol_kind"], top["VERSION"]["symbol_kind"]) == ("function", "class", "variable")

    def test_plugins_module_lists_public_names_by_name_with_stub(self):
        symbols, _ = api("typedlib")

        plugins = rows(symbols, "typedlib.plugins")
        assert set(plugins) == {"Fast", "Alias"}
        assert plugins["Fast"]["audience"] == "public by name, typed, has a stub"

    def test_private_modules_have_no_rows(self):
        symbols, _ = api("typedlib")

        assert "typedlib._core" not in {s["subpath"] for s in symbols}

    def test_one_entry_point_row_for_the_plugin_group(self):
        symbols, _ = api("typedlib")

        found = [s for s in symbols if s["symbol_kind"] == "entry point (demo.plugins)"]
        assert [(s["name"], s["subpath"], s["path"]) for s in found] == [("fast", "typedlib.plugins", "typedlib/pyproject.toml")]

    def test_package_is_the_distribution_name(self):
        symbols, _ = api("typedlib")

        assert {s["package"] for s in symbols} == {"typedlib"}

    def test_every_row_has_the_shared_keys(self):
        symbols, _ = api("typedlib")

        keys = {"kind", "path", "line", "name", "symbol_kind", "package", "subpath", "audience", "external"}
        assert all(set(s) == keys and s["kind"] == "public-api" for s in symbols)


class TestFlatlib:
    def test_star_imports_follow_all_and_underscore_rules(self):
        symbols, _ = api("flatlib")

        top = rows(symbols, "flatlib")
        assert set(top) == {"a", "c"} and {s["audience"] for s in top.values()} == {"public by name"}
        assert (top["a"]["path"], top["c"]["path"]) == ("flatlib/flatlib/one.py", "flatlib/flatlib/two.py")

    def test_submodules_are_import_paths_of_their_own(self):
        symbols, _ = api("flatlib")

        assert set(rows(symbols, "flatlib.one")) == {"a"} and set(rows(symbols, "flatlib.two")) == {"c"}
        assert rows(symbols, "flatlib.one")["a"]["audience"] == "listed in __all__"


class TestBadlib:
    def test_a_computed_all_gives_no_names_and_one_note(self):
        symbols, notes = api("badlib")

        assert symbols == []
        assert notes == [{"kind": "py-note", "path": "badlib/badlib/__init__.py", "note": "api", "name": "badlib|badlib"}]


class TestApplication:
    def test_app_is_not_asked_for_symbols_by_the_caller(self):
        assert py_api.is_library(project("app"), read, TREE) is False


class TestReexportCycle:
    def test_a_cycle_of_reexports_stops_and_marks_the_name_external(self):
        files = {"c/pyproject.toml": '[build-system]\nrequires = []\n[project]\nname = "c"\n',
                 "c/c/__init__.py": "from .a import x\n", "c/c/a.py": "from .b import x\n", "c/c/b.py": "from .a import x\n"}
        tree = frozenset(files)
        proj = py_project.projects(tree)[1]

        symbols, _ = py_api.items(proj, [{"root": "c", "package": "c"}], tree, files.get)

        top = rows(symbols, "c")
        assert top["x"]["path"] is None and top["x"]["external"]

    def test_a_name_imported_from_another_distribution_is_external(self):
        files = {"c/pyproject.toml": '[build-system]\nrequires = []\n[project]\nname = "c"\n',
                 "c/c/__init__.py": "from .a import y\n", "c/c/a.py": "from requests import y\n"}
        tree = frozenset(files)
        proj = py_project.projects(tree)[1]

        symbols, _ = py_api.items(proj, [{"root": "c", "package": "c"}], tree, files.get)

        assert rows(symbols, "c")["y"]["external"] == "requests"

    def test_all_extended_with_a_list_adds_names(self):
        files = {"c/pyproject.toml": '[build-system]\nrequires = []\n[project]\nname = "c"\n',
                 "c/c/__init__.py": "__all__ = ['a']\n__all__ += ['b']\n__all__.extend(['d'])\ndef a(): pass\ndef b(): pass\ndef d(): pass\n"}
        tree = frozenset(files)
        proj = py_project.projects(tree)[1]

        symbols, _ = py_api.items(proj, [{"root": "c", "package": "c"}], tree, files.get)

        assert set(rows(symbols, "c")) == {"a", "b", "d"}

    def test_a_submodule_imported_with_from_dot_is_kind_module(self):
        files = {"c/pyproject.toml": '[build-system]\nrequires = []\n[project]\nname = "c"\n',
                 "c/c/__init__.py": "from . import sub\n", "c/c/sub.py": "Z = 1\n"}
        tree = frozenset(files)
        proj = py_project.projects(tree)[1]

        symbols, _ = py_api.items(proj, [{"root": "c", "package": "c"}], tree, files.get)

        assert rows(symbols, "c")["sub"]["symbol_kind"] == "module"

    def test_a_stub_only_module_is_read_from_the_pyi(self):
        files = {"c/pyproject.toml": '[build-system]\nrequires = []\n[project]\nname = "c"\n',
                 "c/c/__init__.py": "", "c/c/ext.pyi": "def fast() -> int: ...\n"}
        tree = frozenset(files)
        proj = py_project.projects(tree)[1]

        symbols, _ = py_api.items(proj, [{"root": "c", "package": "c"}], tree, files.get)

        assert set(rows(symbols, "c.ext")) == {"fast"}
