import py_project


def projects(*paths):
    return py_project.projects(frozenset(paths), lambda p: None)


def by_dir(found):
    return {p["dir"]: p for p in found}


class TestProjects:
    def test_repository_without_manifests_is_one_root_project(self):
        found = projects("app/main.py", "run.py")

        assert [p["dir"] for p in found] == [""]
        assert found[0]["files"] == ["app/main.py", "run.py"]

    def test_root_is_a_project_even_with_no_python_files(self):
        found = projects("README.md")

        assert [p["dir"] for p in found] == [""] and found[0]["files"] == []

    def test_backend_manifest_beside_frontend_makes_a_second_project(self):
        found = by_dir(projects("backend/pyproject.toml", "backend/app/__init__.py", "backend/app/models.py", "frontend/package.json",
                                "frontend/x.js", "tools.py"))

        assert set(found) == {"", "backend"}
        assert found["backend"]["files"] == ["backend/app/__init__.py", "backend/app/models.py"]
        assert found["backend"]["manifests"] == ["backend/pyproject.toml"]
        assert found[""]["files"] == ["tools.py"]

    def test_requirements_txt_with_a_script_is_a_project(self):
        found = by_dir(projects("tools/requirements.txt", "tools/run.py"))

        assert set(found) == {"", "tools"} and found["tools"]["files"] == ["tools/run.py"]

    def test_nested_project_inside_the_root_project_claims_its_own_files(self):
        found = by_dir(projects("pyproject.toml", "src/a.py", "sub/setup.py", "sub/b.py"))

        assert found[""]["files"] == ["src/a.py"] and found["sub"]["files"] == ["sub/b.py", "sub/setup.py"]
        assert found[""]["manifests"] == ["pyproject.toml"]

    def test_uv_workspace_members_are_separate_projects(self):
        found = projects("pyproject.toml", "packages/a/pyproject.toml", "packages/a/a/x.py", "packages/b/pyproject.toml", "packages/b/b/y.py")

        assert [p["dir"] for p in found] == ["", "packages/a", "packages/b"]

    def test_docs_requirements_with_conf_py_is_a_project(self):
        found = by_dir(projects("docs/requirements.txt", "docs/conf.py"))

        assert "docs" in found

    def test_manifest_folder_without_python_files_is_not_a_project(self):
        found = projects("web/requirements.txt", "web/readme.md")

        assert [p["dir"] for p in found] == [""]

    def test_manifest_folder_with_only_test_files_is_not_a_project(self):
        found = by_dir(projects("lib/pyproject.toml", "lib/test_x.py", "lib/tests/test_y.py"))

        assert set(found) == {""} and found[""]["files"] == ["lib/test_x.py", "lib/tests/test_y.py"]

    def test_manifest_inside_a_test_folder_is_not_a_project(self):
        found = projects("tests/pyproject.toml", "tests/helper.py")

        assert [p["dir"] for p in found] == [""]

    def test_noise_folders_are_ignored(self):
        found = projects("node_modules/x/pyproject.toml", "node_modules/x/a.py", "vendor/y/setup.py", "vendor/y/b.py")

        assert [p["dir"] for p in found] == [""] and found[0]["files"] == []

    def test_files_of_a_dropped_nested_folder_go_to_the_parent(self):
        found = by_dir(projects("a/pyproject.toml", "a/x.py", "a/b/pyproject.toml", "a/b/test_only.py"))

        assert set(found) == {"", "a"} and "a/b/test_only.py" in found["a"]["files"]

    def test_deeper_project_wins_over_shallower(self):
        found = by_dir(projects("a/pyproject.toml", "a/x.py", "a/b/setup.cfg", "a/b/y.py"))

        assert found["a"]["files"] == ["a/x.py"] and found["a/b"]["files"] == ["a/b/y.py"]

    def test_setup_py_alone_does_not_make_a_project(self):
        found = projects("lib/setup.py")

        assert [p["dir"] for p in found] == [""]
