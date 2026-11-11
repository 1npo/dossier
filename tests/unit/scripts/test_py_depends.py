import py_depends

MODULES = {"app": "app/__init__.py", "app.deps": "app/deps.py", "app.routes": "app/routes.py", "app.sub.api": "app/sub/api.py"}
PATHS = {p: m for m, p in MODULES.items()}


def edges(source, path="app/routes.py"):
    return py_depends.edges([path], lambda p: source, MODULES, PATHS)


def pairs(items):
    return [(e["from"], e["to"], e["paths"][0], e["line"], e["count"]) for e in items]


class TestEdges:
    def test_name_imported_from_a_project_module_gives_an_edge_from_the_function(self):
        src = "from fastapi import Depends\nfrom app.deps import get_db\n\n\ndef items(db=Depends(get_db)): ...\n"

        assert pairs(edges(src)) == [("items", "get_db", "app/deps.py", 5, 1)]

    def test_relative_import_of_a_module_and_attribute_use(self):
        src = "from fastapi import Depends\nfrom . import deps\n\n\ndef me(u=Depends(deps.current_user)): ...\n"

        assert pairs(edges(src)) == [("me", "deps.current_user", "app/deps.py", 5, 1)]

    def test_relative_import_from_a_nested_package(self):
        src = "from fastapi import Depends\nfrom ..deps import get_db\n\n\nasync def a(db=Depends(get_db)): ...\n"

        assert pairs(edges(src, "app/sub/api.py")) == [("a", "get_db", "app/deps.py", 5, 1)]

    def test_annotated_and_decorator_dependencies_are_found(self):
        src = ("from typing import Annotated\nfrom fastapi import Depends\nfrom app.deps import get_db, current_user\n\n\n"
               "@r.get('/', dependencies=[Depends(get_db)])\ndef a(u: Annotated[str, Depends(current_user)]): ...\n")

        assert sorted(e["to"] for e in edges(src)) == ["current_user", "get_db"]

    def test_the_same_dependency_twice_in_a_function_is_counted(self):
        src = "from fastapi import Depends\nfrom app.deps import get_db\n\n\ndef a(x=Depends(get_db), y=Depends(get_db)): ...\n"

        assert pairs(edges(src)) == [("a", "get_db", "app/deps.py", 5, 2)]

    def test_fastapi_dot_depends_is_recognised(self):
        src = "import fastapi\nfrom app.deps import get_db\n\n\ndef a(x=fastapi.Depends(get_db)): ...\n"

        assert len(edges(src)) == 1

    def test_security_is_matched_like_depends_and_scopes_are_ignored(self):
        src = ("from fastapi import Security\nfrom app.deps import current_user\n\n\n"
               "def a(u=Security(current_user, scopes=['items'])): ...\n")

        assert pairs(edges(src)) == [("a", "current_user", "app/deps.py", 5, 1)]

    def test_fastapi_dot_security_is_recognised(self):
        src = "import fastapi\nfrom app.deps import current_user\n\n\ndef a(u=fastapi.Security(current_user)): ...\n"

        assert len(edges(src)) == 1

    def test_an_instance_stands_for_its_class(self):
        src = "from fastapi import Depends, Security\nfrom app.deps import Auth\n\n\ndef a(x=Depends(Auth()), y=Security(Auth(scopes=['a']))): ...\n"

        assert pairs(edges(src)) == [("a", "Auth", "app/deps.py", 5, 2)]

    def test_an_instance_through_a_module_attribute(self):
        src = "from fastapi import Depends\nfrom . import deps\n\n\ndef a(x=Depends(deps.Auth())): ...\n"

        assert pairs(edges(src)) == [("a", "deps.Auth", "app/deps.py", 5, 1)]

    def test_the_dependency_keyword_is_read(self):
        src = "from fastapi import Depends\nfrom app.deps import get_db\n\n\ndef a(x=Depends(dependency=get_db)): ...\n"

        assert len(edges(src)) == 1

    def test_an_instance_of_a_same_file_or_outside_class_gives_no_edge(self):
        src = ("from fastapi import Depends\nfrom requests import Session\n\n\nclass Local: ...\n\n\n"
               "def a(x=Depends(Local()), y=Depends(Session()), z=Depends()): ...\n")

        assert edges(src) == []

    def test_same_file_lambda_outside_project_and_class_free_names_give_no_edge(self):
        src = ("from fastapi import Depends\nfrom requests import get\n\n\ndef local(): ...\n\n\n"
               "def a(x=Depends(local), y=Depends(lambda: 1), z=Depends(get), w=Depends(missing)): ...\n")

        assert edges(src) == []

    def test_dependency_outside_a_function_has_no_route_to_attach_to(self):
        src = "from fastapi import APIRouter, Depends\nfrom app.deps import get_db\n\nr = APIRouter(dependencies=[Depends(get_db)])\n"

        assert edges(src) == []

    def test_a_file_that_does_not_parse_is_skipped(self):
        assert edges("def (:\n") == []

    def test_a_function_nested_in_a_function_is_not_counted_for_the_outer_one(self):
        src = "from fastapi import Depends\nfrom app.deps import get_db\n\n\ndef outer():\n    def inner(x=Depends(get_db)): ...\n"

        assert pairs(edges(src)) == [("inner", "get_db", "app/deps.py", 6, 1)]
