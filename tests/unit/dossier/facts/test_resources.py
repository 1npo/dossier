from dossier.facts import resources

TREE = frozenset({
    "app/mailer.py", "app/data/email_templates/welcome.mjml", "app/data/email_templates/reset.mjml", "app/data/email_templates/bye.mjml",
    "app/data/mime_data.json", "app/other.py", "docs/guide.md", "pyproject.toml", "tests/test_mail.py", "tests/data/sample.json",
    "assets/notes.txt", "README.md",
})
SOURCES = {
    "app/mailer.py": "def render(kind):\n    path = base / 'data' / 'email_templates'\n    return load(f'email_templates/{kind}.mjml')\n"
                     "MIME = pkgutil.get_data('app', 'data/mime_data.json')\n",
    "app/other.py": "x = 1\n",
    "tests/test_mail.py": "open('tests/data/sample.json')\n",
}


def find(tree=TREE, sources=SOURCES):
    return resources.detect(tree, sources.get)


def test_three_templates_in_one_folder_are_one_group_with_their_reader():
    items = {i["name"]: i for i in find()}

    group = items["app/data/email_templates/*.mjml"]
    assert group["count"] == 3 and len(group["members"]) == 3
    assert group["referenced_by"][0]["path"] == "app/mailer.py"
    assert "no code was found" not in group["display"]


def test_a_json_file_read_by_name_is_a_group_of_its_own():
    items = {i["name"]: i for i in find()}

    assert items["app/data/*.json"]["referenced_by"][0]["how"] in ("file name", "package resource call")


def test_documentation_manifests_and_root_files_are_not_resources():
    names = {i["name"] for i in find()}

    assert not any(n.startswith(("docs/", "pyproject", "README")) for n in names) and "*.md" not in names


def test_a_test_data_file_read_only_by_a_test_is_left_out():
    assert not [i for i in find() if i["path"].startswith("tests/")]


def test_a_group_in_a_data_folder_that_no_code_reads_is_still_listed_with_no_readers():
    items = find(sources={"app/mailer.py": "x = 1\n"})

    group = next(i for i in items if i["name"] == "app/data/*.json")
    assert group["referenced_by"] == [] and "no code was found" in group["display"]
