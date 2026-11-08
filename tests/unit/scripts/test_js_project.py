import json

import js_project


def tree_of(files: dict):
    """(tracked paths, read function) from a {path: text} dict."""
    return sorted(files), (lambda p: files.get(p))


def pkg(name=None, **kw):
    return json.dumps({**({"name": name} if name else {}), **kw})


def find(projects, dir_):
    return next(p for p in projects if p["dir"] == dir_)


class TestReadJson:
    def test_reads_an_object(self):
        assert js_project.read_json({"a/package.json": '{"x": 1}'}.get, "a/package.json") == {"x": 1}

    def test_bad_json_missing_file_and_non_object_give_none(self):
        read = {"bad": "{", "list": "[1]"}.get

        assert [js_project.read_json(read, p) for p in ("bad", "list", "nope")] == [None, None, None]


class TestProjects:
    def test_one_package_with_a_lockfile_is_one_project(self):
        tree, read = tree_of({"package.json": pkg("rw"), "package-lock.json": "{}", "src/a.ts": "", "src/b.js": "",
                              "e2e/project.json": "{}", "e2e/x.spec.ts": "", "README.md": ""})

        got = js_project.projects(tree, read)

        assert [(p["dir"], p["package"], p["lockfile"], p["manager"]) for p in got] == [("", "rw", "package-lock.json", "npm")]
        assert got[0]["members"] == [""] and got[0]["files"] == ["e2e/x.spec.ts", "src/a.ts", "src/b.js"]

    def test_three_apps_with_their_own_yarn_lock_are_three_projects_and_the_empty_root_is_dropped(self):
        files = {"package.json": pkg("root"), "README.md": ""}
        for app in ("react-vite", "nextjs", "react-router"):
            files[f"apps/{app}/package.json"] = pkg(app)
            files[f"apps/{app}/yarn.lock"] = "# yarn lockfile v1"
            files[f"apps/{app}/src/main.tsx"] = ""
        tree, read = tree_of(files)

        got = js_project.projects(tree, read)

        assert [p["dir"] for p in got] == ["apps/nextjs", "apps/react-router", "apps/react-vite"]
        assert {p["manager"] for p in got} == {"yarn"}
        assert find(got, "apps/nextjs")["files"] == ["apps/nextjs/src/main.tsx"]

    def test_a_project_below_the_root_is_a_member_of_itself(self):
        tree, read = tree_of({"apps/web/package.json": pkg("web"), "apps/web/yarn.lock": "", "apps/web/src/a.ts": ""})

        got = js_project.projects(tree, read)

        assert find(got, "apps/web")["members"] == ["apps/web"]

    def test_npm_workspaces_make_one_project_with_members(self):
        tree, read = tree_of({"package.json": pkg("mono", workspaces=["packages/*"]), "package-lock.json": "{}",
                              "packages/a/package.json": pkg("a"), "packages/a/src/i.ts": "",
                              "packages/b/package.json": pkg("b"), "packages/b/src/i.ts": ""})

        got = js_project.projects(tree, read)

        assert [p["dir"] for p in got] == [""]
        assert got[0]["members"] == ["", "packages/a", "packages/b"]
        assert got[0]["files"] == ["packages/a/src/i.ts", "packages/b/src/i.ts"]

    def test_workspaces_written_as_an_object(self):
        tree, read = tree_of({"package.json": pkg("m", workspaces={"packages": ["libs/*"]}),
                              "libs/a/package.json": pkg("a"), "libs/a/i.ts": ""})

        got = js_project.projects(tree, read)

        assert [(p["dir"], p["members"]) for p in got] == [("", ["", "libs/a"])]

    def test_pnpm_workspace_file_makes_the_root_a_workspace(self):
        tree, read = tree_of({"package.json": pkg("m"), "pnpm-workspace.yaml": "packages:\n  - 'packages/*'\n", "pnpm-lock.yaml": "",
                              "packages/a/package.json": pkg("a"), "packages/a/i.ts": ""})

        got = js_project.projects(tree, read)

        assert [(p["dir"], p["manager"], p["members"]) for p in got] == [("", "pnpm", ["", "packages/a"])]

    def test_a_member_with_its_own_lockfile_is_its_own_project(self):
        tree, read = tree_of({"package.json": pkg("m", workspaces=["a"]), "package-lock.json": "{}", "i.ts": "",
                              "a/package.json": pkg("a"), "a/yarn.lock": "", "a/i.ts": ""})

        got = js_project.projects(tree, read)

        assert [p["dir"] for p in got] == ["", "a"] and find(got, "")["files"] == ["i.ts"]

    def test_no_package_json_at_all_gives_a_virtual_project(self):
        tree, read = tree_of({"src/a.js": "", "b.ts": "", "x.py": ""})

        got = js_project.projects(tree, read)

        assert len(got) == 1
        assert (got[0]["dir"], got[0]["package"], got[0]["lockfile"], got[0]["manager"]) == ("", None, None, None)
        assert got[0]["files"] == ["b.ts", "src/a.js"] and got[0]["members"] == []

    def test_files_outside_every_project_join_a_virtual_one(self):
        tree, read = tree_of({"app/package.json": pkg("app"), "app/package-lock.json": "{}", "app/i.ts": "", "scripts/tool.js": ""})

        got = js_project.projects(tree, read)

        assert [(p["dir"], p["package"]) for p in got] == [("", None), ("app", "app")]
        assert find(got, "")["files"] == ["scripts/tool.js"]

    def test_vendored_and_generated_files_and_packages_are_ignored(self):
        tree, read = tree_of({"package.json": pkg("r"), "package-lock.json": "{}", "src/a.ts": "", "dist/a.js": "",
                              "node_modules/x/package.json": pkg("x"), "node_modules/x/index.js": "", "x.min.js": ""})

        got = js_project.projects(tree, read)

        assert [p["dir"] for p in got] == [""] and got[0]["files"] == ["src/a.ts"] and got[0]["members"] == [""]

    def test_bun_lockfile_gives_the_bun_manager(self):
        for lock in ("bun.lockb", "bun.lock"):
            tree, read = tree_of({"package.json": pkg("b"), lock: "", "i.ts": ""})

            assert js_project.projects(tree, read)[0]["manager"] == "bun"

    def test_unreadable_package_json_still_makes_a_package(self):
        tree, read = tree_of({"package.json": "{", "yarn.lock": "", "i.ts": ""})

        got = js_project.projects(tree, read)

        assert (got[0]["dir"], got[0]["package"], got[0]["manager"]) == ("", None, "yarn")


class TestSourceRoots:
    def test_one_project_uses_src_when_it_holds_files(self):
        tree, read = tree_of({"package.json": pkg("r"), "package-lock.json": "{}", "src/a.ts": ""})

        got = js_project.source_roots(js_project.projects(tree, read), tree)

        assert got == [{"kind": "source-root", "path": "package.json", "root": "src"}]

    def test_one_project_without_src_uses_its_folder(self):
        tree, read = tree_of({"app/package.json": pkg("a"), "app/yarn.lock": "", "app/lib/a.ts": ""})

        got = js_project.source_roots(js_project.projects(tree, read), tree)

        assert got == [{"kind": "source-root", "path": "app/package.json", "root": "app"}]

    def test_several_projects_get_their_parent_folder(self):
        files = {}
        for app in ("a", "b"):
            files.update({f"apps/{app}/package.json": pkg(app), f"apps/{app}/yarn.lock": "", f"apps/{app}/src/m.ts": ""})
        tree, read = tree_of(files)

        got = js_project.source_roots(js_project.projects(tree, read), tree)

        assert [(g["path"], g["root"]) for g in got] == [("apps/a/package.json", "apps"), ("apps/b/package.json", "apps")]

    def test_a_project_at_the_root_gets_none_and_a_top_level_folder_is_its_own_area_when_there_are_several(self):
        tree, read = tree_of({"package.json": pkg("r"), "package-lock.json": "{}", "i.ts": "",
                              "tools/package.json": pkg("t"), "tools/yarn.lock": "", "tools/j.ts": ""})

        got = js_project.source_roots(js_project.projects(tree, read), tree)

        assert [(g["path"], g["root"]) for g in got] == [("tools/package.json", "tools")]

    def test_virtual_project_names_its_first_file(self):
        tree, read = tree_of({"src/a.js": "", "src/b.js": ""})

        got = js_project.source_roots(js_project.projects(tree, read), tree)

        assert got == [{"kind": "source-root", "path": "src/a.js", "root": "src"}]

    def test_no_projects_no_roots(self):
        assert js_project.source_roots([], []) == []


class TestManifestFrameworks:
    def test_names_unsupported_frameworks_sorted_and_once(self):
        tree, read = tree_of({"package.json": pkg("r", dependencies={"koa": "2", "express": "4"}, devDependencies={"astro": "4"}),
                              "package-lock.json": "{}", "i.ts": ""})

        assert js_project.manifest_frameworks(js_project.projects(tree, read), read) == ["Astro", "Koa"]

    def test_scoped_packages_and_members_count(self):
        tree, read = tree_of({"package.json": pkg("m", workspaces=["p/*"]), "package-lock.json": "{}",
                              "p/a/package.json": pkg("a", dependencies={"@remix-run/react": "2", "@angular/core": "17"}),
                              "p/b/package.json": pkg("b", dependencies={"@hapi/hapi": "21", "@sveltejs/kit": "2", "hono": "4", "nuxt": "3"}),
                              "p/a/i.ts": ""})

        got = js_project.manifest_frameworks(js_project.projects(tree, read), read)

        assert got == ["Angular", "Hapi", "Hono", "Nuxt", "Remix", "SvelteKit"]

    def test_supported_frameworks_are_not_named(self):
        tree, read = tree_of({"package.json": pkg("r", dependencies={"express": "4", "next": "14", "fastify": "4", "react": "18"}),
                              "package-lock.json": "{}", "i.ts": ""})

        assert js_project.manifest_frameworks(js_project.projects(tree, read), read) == []
