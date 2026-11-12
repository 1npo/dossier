"""The package's shape: the dependency order of its subpackages (D4 of plan 014), the rules inside them,
empty `__init__` files, no import of a pre-package flat module name, two launchers in scripts/, and the
one module that builds paths from `__file__`."""
import ast
import re
import subprocess

from paths import SKILL_ROOT as ROOT

PACKAGE = ROOT / "src" / "dossier"

# Subpackage -> the subpackages it may import besides itself (D4). `cli` and `__main__` may import anything.
MAY_IMPORT = {
    "resources": set(),
    "core": {"resources"},
    "facts": {"resources", "core"},
    "tooling": {"resources", "core", "facts"},
    "findings": {"resources", "core", "facts"},
    "history": {"resources", "core", "facts", "findings"},
    "adapters": {"resources", "core", "facts", "tooling", "findings"},
    "render": {"resources", "core", "facts", "tooling", "findings", "history"},
    "checks": {"resources", "core", "facts", "findings", "render"},
    "pipeline": {"resources", "core", "facts", "tooling", "findings", "adapters", "render"},
}
ANYTHING = {"cli", "__main__", "__init__"}
LANGUAGES = ("dossier.adapters.python", "dossier.adapters.js", "dossier.adapters.csharp")

# Every flat module name of scripts/ before the package (the union of the Phase C maps, and A4's `dossier`).
FLAT_NAMES = frozenset("""
    adapters buildlog candidates candidates_history check_layout check_page checks checks_people checks_v3 checks_v7
    components config cs_adapter cs_api cs_entries cs_graph cs_models cs_project cs_queries cs_scip cs_sdk cs_semgrep
    cs_tests deps dossier env_scan gather github_owners graphs history incremental js_adapter js_api js_entries
    js_prisma js_project js_queries js_reduce js_semgrep js_tools markers measured measured_blast measured_change
    measured_cs measured_env measured_er measured_graph measured_js measured_people measured_tables measured_upgrade
    ownership page_audit portfolio process py_adapter py_api py_depends py_packages py_project py_queries py_tools
    render repo_adapter resolve restore sandbox schema scip_read scip_tool shared_tools stages summary summary_check
    tier_b toolcheck verify viewer workarea workflow
""".split())

# Only resources.py and the two launchers may use `__file__`; render.page reads `module.__file__` of the
# three embedded modules. tools/bump_version.py is a maintainer tool, outside this scan.
ALLOWED_FILE_USERS = {"src/dossier/resources.py", "scripts/dossier.py", "scripts/check_page.py"}
FILE_NAME = re.compile(r"(?<![\w.])__file__\b")
MODULE_FILE = re.compile(r"\bmodule\.__file__\b")


def package_modules():
    """(dotted name, path) of every module of the package, package data left out."""
    out = []
    for path in sorted(PACKAGE.rglob("*.py")):
        rel = path.relative_to(PACKAGE.parent)
        if "data" in rel.parts[1:2]:
            continue
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        out.append((".".join(parts), path))
    return out


MODULES = package_modules()
NAMES = {name for name, _ in MODULES}


def imported(tree):
    """(line, dotted module) of every dossier module a source imports, at any depth."""
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out += [(n.lineno, a.name) for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            for a in n.names:
                full = f"{n.module}.{a.name}"
                out.append((n.lineno, full if full in NAMES else n.module))
    return [(line, m) for line, m in out if m == "dossier" or m.startswith("dossier.")]


def layer_of(module):
    parts = module.split(".")
    return parts[1] if len(parts) > 1 else "__init__"


def edges():
    """(importer, line, imported) for every import between dossier modules."""
    out = []
    for name, path in MODULES:
        for line, other in imported(ast.parse(path.read_text(encoding="utf-8"))):
            out.append((name, line, other))
    return out


EDGES = edges()


def tracked_python(*folders):
    files = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--", *folders], capture_output=True, text=True,
                           check=True).stdout.split()
    return [ROOT / f for f in files if f.endswith(".py") and not f.startswith(("tests/fixtures/", "src/dossier/data/"))
            and (ROOT / f).exists()]


def file_users():
    found = list(PACKAGE.rglob("*.py")) + list((ROOT / "scripts").glob("*.py"))
    return sorted(p for p in found if p.relative_to(ROOT).as_posix() not in ALLOWED_FILE_USERS)


class TestDependencyOrder:
    def test_every_subpackage_imports_only_the_ones_below_it(self):
        bad = [f"{a}:{line} imports {b}" for a, line, b in EDGES
               if layer_of(a) not in ANYTHING and layer_of(b) != layer_of(a)
               and layer_of(b) not in MAY_IMPORT[layer_of(a)]]

        assert bad == []

    def test_nothing_in_the_package_imports_the_command_line(self):
        bad = [f"{a}:{line}" for a, line, b in EDGES if layer_of(b) == "cli" and layer_of(a) not in ANYTHING]

        assert bad == []

    def test_the_table_names_every_subpackage(self):
        layers = {layer_of(name) for name in NAMES}

        assert layers - ANYTHING == set(MAY_IMPORT)


class TestRulesInsideSubpackages:
    def test_render_markup_imports_nothing_from_render(self):
        bad = [b for a, _, b in EDGES if a == "dossier.render.markup" and b.startswith("dossier.render")]

        assert bad == []

    def test_measured_cards_never_import_the_page(self):
        bad = [f"{a}:{line}" for a, line, b in EDGES if a.startswith("dossier.render.measured") and b == "dossier.render.page"]

        assert bad == []

    def test_the_adapter_base_imports_no_adapter(self):
        bad = [b for a, _, b in EDGES if a == "dossier.adapters.base" and b.startswith("dossier.adapters")]

        assert bad == []

    def test_language_adapters_never_import_one_another(self):
        bad = [f"{a}:{line} imports {b}" for a, line, b in EDGES for lang in LANGUAGES
               if a.startswith(lang) and b.startswith(LANGUAGES) and not b.startswith(lang)]

        assert bad == []


class TestInitFiles:
    INITS = [path for _, path in MODULES if path.name == "__init__.py"]

    def test_every_init_has_a_docstring(self):
        bad = [p.relative_to(ROOT).as_posix() for p in self.INITS if not ast.get_docstring(ast.parse(p.read_text()))]

        assert bad == []

    def test_every_init_lists_its_modules_in_all(self):
        bad = []
        for p in self.INITS:
            tree = ast.parse(p.read_text())
            names = [t.id for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))
                     for t in (n.targets if isinstance(n, ast.Assign) else [n.target]) if isinstance(t, ast.Name)]
            if "__all__" not in names:
                bad.append(p.relative_to(ROOT).as_posix())

        assert bad == []

    def test_no_init_imports_at_module_level(self):
        # cli/__init__.py's main() imports the parser when it is called, which is allowed: importing the package
        # must not pull in Pygments, because scripts/check_page.py runs without it (R17).
        bad = [f"{p.relative_to(ROOT).as_posix()}:{n.lineno}" for p in self.INITS for n in ast.parse(p.read_text()).body
               if isinstance(n, (ast.Import, ast.ImportFrom)) and not (isinstance(n, ast.ImportFrom) and n.module == "__future__")]

        assert bad == []


class TestNoFlatImports:
    def test_no_source_imports_a_pre_package_module_name(self):
        bad = []
        for path in tracked_python("src", "scripts", "tests", "tools"):
            for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(n, ast.Import):
                    hits = [a.name for a in n.names if a.name in FLAT_NAMES]
                elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module in FLAT_NAMES:
                    # `from dossier import x` names the package when x is one of its modules
                    hits = [] if n.module == "dossier" and all(f"dossier.{a.name}" in NAMES for a in n.names) else [n.module]
                else:
                    continue
                bad += [f"{path.relative_to(ROOT).as_posix()}:{n.lineno} {h}" for h in hits]

        assert bad == []


class TestScripts:
    def test_scripts_holds_exactly_the_two_launchers(self):
        files = subprocess.run(["git", "-C", str(ROOT), "ls-files", "scripts"], capture_output=True, text=True,
                               check=True).stdout.split()

        assert files == ["scripts/check_page.py", "scripts/dossier.py"]


class TestNoFilePaths:
    def test_only_the_resources_module_and_the_launchers_use_the_file_name(self):
        offenders = []
        for path in file_users():
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if FILE_NAME.search(line) and not MODULE_FILE.search(line):
                    offenders.append(f"{path.relative_to(ROOT).as_posix()}:{n}")

        assert offenders == []

    def test_the_module_attribute_is_used_only_by_the_gatherer_reader(self):
        users = [p.relative_to(ROOT).as_posix() for p in file_users() if MODULE_FILE.search(p.read_text(encoding="utf-8"))]

        assert users == ["src/dossier/render/page.py"]
