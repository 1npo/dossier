import json
import re
import subprocess

import pytest

from conftest import JSFIX, key_line, line_of

MARKERS = """ci-jest prisma-env model-user
ep-root io-env ep-listen io-log bs-mount ep-get ep-post bs-route io-error not-route
io-db io-outbound fail-tx fail-catch import-up io-db-connect cycle-a cycle-b
model-order model-item model-orm bs-barrel bs-import bs-require bs-di state-let state-map
ep-cli io-exit ep-cron ep-queue bs-flag
ui-literal ui-constant ui-computed bs-context bs-hook test-vi-mock test-skip
api-reexport api-rename api-own api-deep api-hidden api-wild
test-mock test-todo""".split()


def all_files():
    return [p for p in JSFIX.rglob("*") if p.is_file() and "node_modules" not in p.parts]


class TestJsFixture:
    @pytest.mark.parametrize("name", MARKERS)
    def test_marker_appears_exactly_once_in_the_fixture(self, name):
        pattern = re.compile(r"@" + re.escape(name) + r"(?![\w-])")

        count = sum(len(pattern.findall(p.read_text(encoding="utf-8"))) for p in all_files())

        assert count == 1

    def test_every_file_is_under_forty_lines(self):
        long = [str(p.relative_to(JSFIX)) for p in all_files() if p.name != "package-lock.json" and len(p.read_text().splitlines()) >= 40]

        assert long == []

    def test_line_of_and_key_line_find_lines(self, js_repo):
        assert js_repo.line_of("src/main.ts", "ep-root") == 8
        assert js_repo.key_line("package.json", "bin") == key_line(JSFIX, "package.json", "bin")
        with pytest.raises(LookupError):
            js_repo.key_line("package.json", "nope")

    def test_it_is_a_git_repository_with_one_commit(self, js_repo):
        count = subprocess.run(["git", "-C", js_repo.path, "rev-list", "--count", "HEAD"], capture_output=True, text=True).stdout.strip()

        assert count == "1" and len(js_repo.sha) == 40

    def test_node_modules_are_never_copied_into_the_repository(self, tmp_path):
        from conftest import _commit_fixture
        src = tmp_path / "src"
        (src / "node_modules/x").mkdir(parents=True)
        (src / "node_modules/x/index.js").write_text("")
        (src / "a.js").write_text("")

        repo = _commit_fixture(src, tmp_path / "out", "r")

        assert subprocess.run(["git", "-C", repo.path, "ls-files"], capture_output=True, text=True).stdout.split() == ["a.js"]


class TestShape:
    def test_lockfile_lists_express_as_a_local_stub_so_install_needs_no_network(self):
        lock = json.loads((JSFIX / "package-lock.json").read_text())

        assert lock["packages"]["node_modules/express"]["resolved"] == "stubs/express"
        assert not [p for p in lock["packages"].values() if str(p.get("resolved", "")).startswith("http")]

    def test_the_two_cycle_pairs_exist(self):
        assert "'./b'" in (JSFIX / "src/a.ts").read_text() and "'./a'" in (JSFIX / "src/b.ts").read_text()
        assert "import type" in (JSFIX / "src/c.ts").read_text() and "import type" in (JSFIX / "src/d.ts").read_text()

    def test_the_lib_package_declares_its_api_through_exports(self):
        exports = json.loads((JSFIX / "packages/lib/package.json").read_text())["exports"]

        assert set(exports) == {".", "./utils/*", "./internal/*"} and exports["./internal/*"] is None

    def test_site_has_both_next_routers_and_brackets_and_parentheses_in_a_folder_name(self):
        names = {str(p.relative_to(JSFIX / "packages/site")) for p in (JSFIX / "packages/site").rglob("*.ts*")}

        assert {"app/page.tsx", "app/(shop)/items/[id]/page.tsx", "app/api/ping/route.ts", "pages/about.tsx", "pages/_app.tsx"} <= names

    def test_markers_survive_through_line_of(self):
        assert line_of(JSFIX, "src/users/controller.ts", "ep-post") > line_of(JSFIX, "src/users/controller.ts", "ep-get")
