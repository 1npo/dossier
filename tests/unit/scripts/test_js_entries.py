import json
import subprocess
from pathlib import Path

import js_entries
import js_project


def tracked(root):
    return frozenset(subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True).stdout.split())


def reader(root):
    def read(path):
        try:
            return (Path(root) / path).read_text(encoding="utf-8")
        except OSError:
            return None
    return read


def by_kind(items, kind):
    return [i for i in items if i["kind"] == kind]


class TestPackageEntries:
    def entries(self, js_repo, folder=""):
        project = {"dir": folder, "members": [folder]}
        return js_entries.package_entries(project, reader(js_repo.path))

    def test_bin_is_a_command_at_the_line_of_its_entry(self, js_repo):
        got = by_kind(self.entries(js_repo), "package-bin")

        assert len(got) == 1
        e = got[0]
        assert (e["path"], e["name"], e["target"], e["trigger"]) == ("package.json", "shopjs", "dist/cli.js", "the `shopjs` command")
        assert e["line"] == e["end_line"] == js_repo.key_line("package.json", "bin") + 1
        assert e["rule"] == "js.package-bin"

    def test_scripts_are_named_by_package_and_script(self, js_repo):
        got = {e["name"]: e for e in by_kind(self.entries(js_repo), "package-script")}

        assert set(got) == {"shopjs start", "shopjs test", "prisma seed"}
        assert got["shopjs start"]["line"] == js_repo.key_line("package.json", "start")
        assert got["shopjs start"]["trigger"] == "running `start` with the package manager"
        assert got["shopjs start"]["target"] == "node dist/main.js"
        assert got["shopjs test"]["line"] == js_repo.key_line("package.json", "test")
        assert got["prisma seed"]["line"] == js_repo.key_line("package.json", "seed")
        assert got["prisma seed"]["target"] == "ts-node prisma/seed.ts"
        assert got["prisma seed"]["trigger"] == "running `prisma seed` with the package manager"

    def test_main_is_an_entry_for_whoever_imports_the_package(self, js_repo):
        got = by_kind(self.entries(js_repo), "package-main")

        assert [(e["name"], e["line"], e["trigger"]) for e in got] == [
            ("dist/main.js", js_repo.key_line("package.json", "main"), "when another program imports or runs this package")]

    def test_exports_dot_conditions_use_the_first_string_target(self, js_repo):
        got = by_kind(self.entries(js_repo, "packages/lib"), "package-main")

        assert [e["name"] for e in got] == ["./dist/index.d.ts"]
        assert got[0]["path"] == "packages/lib/package.json"

    def test_module_and_a_plain_exports_string_each_count(self):
        files = {"package.json": json.dumps({"name": "p", "module": "./m.js", "exports": "./e.js"}, indent=2)}

        got = js_entries.package_entries({"dir": "", "members": [""]}, files.get)

        assert [e["name"] for e in by_kind(got, "package-main")] == ["./m.js", "./e.js"]

    def test_bin_as_a_string_is_named_by_the_package(self):
        files = {"package.json": '{\n  "name": "tool",\n  "bin": "cli.js"\n}\n'}

        got = js_entries.package_entries({"dir": "", "members": [""]}, files.get)

        assert [(e["name"], e["target"], e["line"]) for e in by_kind(got, "package-bin")] == [("tool", "cli.js", 3)]

    def test_every_member_package_is_read_and_a_missing_manifest_is_skipped(self):
        files = {"a/package.json": '{"name": "a", "scripts": {"x": "y"}}', "b/package.json": "{"}

        got = js_entries.package_entries({"dir": "", "members": ["a", "b", "c"]}, files.get)

        assert [(e["name"], e["path"]) for e in got] == [("a x", "a/package.json")]

    def test_the_snippet_shows_the_line(self, js_repo):
        script = next(e for e in self.entries(js_repo) if e["name"] == "shopjs start")

        assert script["snippet"] == "start: node dist/main.js"


class TestNxTargets:
    def test_targets_are_named_project_colon_target(self, js_repo):
        got = js_entries.nx_targets(tracked(js_repo.path), reader(js_repo.path))

        assert [(e["name"], e["kind"], e["trigger"], e["target"]) for e in got] == [
            ("shopjs:build", "nx-target", "running `nx build`", "tsc -p tsconfig.app.json"),
            ("shopjs:serve", "nx-target", "running `nx serve`", "node dist/main.js")]
        assert got[0]["line"] == js_repo.key_line("project.json", "build") and got[0]["path"] == "project.json"

    def test_a_project_without_a_name_uses_its_folder(self):
        files = {"apps/web/project.json": '{"targets": {"lint": {"executor": "@nx/eslint:lint"}}}'}

        got = js_entries.nx_targets(frozenset(files), files.get)

        assert [(e["name"], e["target"]) for e in got] == [("web:lint", "@nx/eslint:lint")]

    def test_vendored_project_files_are_ignored(self):
        files = {"node_modules/x/project.json": '{"name": "x", "targets": {"a": {}}}'}

        assert js_entries.nx_targets(frozenset(files), files.get) == []


class TestNextRoutes:
    def routes(self, js_repo):
        files = [f for f in tracked(js_repo.path) if f.startswith("packages/site/")]
        return js_entries.next_routes(files, {"dir": "packages/site"})

    def test_pages_and_api_routes_from_both_routers(self, js_repo):
        got = {e["name"]: e for e in self.routes(js_repo)}

        assert set(got) == {"/", "/items/[id]", "API /api/ping", "/about"}
        assert got["/about"]["path"] == "packages/site/pages/about.tsx"
        assert got["/items/[id]"]["path"] == "packages/site/app/(shop)/items/[id]/page.tsx"
        assert {e["kind"] for e in got.values()} == {"http-route"} and {e["rule"] for e in got.values()} == {"js.next-route"}
        assert got["API /api/ping"]["trigger"] == "a web request to `API /api/ping`"

    def test_app_wrapper_files_are_not_routes(self, js_repo):
        assert not [e for e in self.routes(js_repo) if "_app" in e["path"]]

    def test_rules_for_src_folders_index_pages_groups_and_private_folders(self):
        files = ["w/src/app/page.js", "w/src/app/(g)/team/page.tsx", "w/src/app/_private/page.tsx", "w/src/app/@slot/page.tsx",
                 "w/src/pages/index.tsx", "w/src/pages/blog/index.tsx", "w/src/pages/api/users.ts", "w/src/pages/_document.tsx",
                 "w/src/pages/_error.tsx", "w/src/pages/blog/post.test.tsx", "w/src/app/layout.tsx", "w/src/app/api/x/route.ts",
                 "w/lib/pages/ignored.tsx", "other/pages/not-mine.tsx"]

        got = sorted(e["name"] for e in js_entries.next_routes(files, {"dir": "w"}))

        assert got == ["/", "/", "/blog", "/team", "API /api/users", "API /api/x"]

    def test_a_package_at_the_repository_root(self):
        got = js_entries.next_routes(["app/page.tsx", "pages/a.ts", "node_modules/x/pages/b.ts"], {"dir": ""})

        assert sorted(e["name"] for e in got) == ["/", "/a"]
