from dossier.adapters.csharp import entries as cs_entries
from test_cs_adapter import extract


def tasks(files):
    return [(r["name"], r["line"]) for r in cs_entries.cake_tasks(sorted(files), files.get)]


class TestCakeTasks:
    def test_each_task_declaration_is_a_build_task_at_its_line(self):
        text = 'Task("Clean");\n\nTask("Build")\n    .IsDependentOn("Clean");\n'

        assert tasks({"build.cake": text}) == [("Clean", 1), ("Build", 3)]

    def test_a_dependency_is_not_a_task_and_commented_tasks_are_skipped(self):
        text = '// Task("Line")\n/* Task("Block")\n   Task("Inner") */\nTask("Real").IsDependentOn("Other");\n'

        assert tasks({"build.cake": text}) == [("Real", 4)]

    def test_single_quoted_names_and_a_name_in_a_variable(self):
        text = "Task('Test');\nTask(name);\n"

        assert tasks({"build.cake": text}) == [("Test", 1)]

    def test_only_cake_files_are_read(self):
        assert tasks({"build.cs": 'Task("A");', "notes.txt": 'Task("B");', "tools/x.cake": 'Task("C");'}) == [("C", 1)]

    def test_row_fields(self):
        row = cs_entries.cake_tasks(["build.cake"], {"build.cake": 'Task("Pack");'}.get)[0]

        assert (row["kind"], row["name"], row["path"], row["target"], row["rule"], row["snippet"]) == (
            "build-task", "Pack", "build.cake", "build.cake", "cs.cake-task", 'Task("Pack")')
        assert row["trigger"] == "running `dotnet cake --target Pack`"


class TestCakeInTheAdapter:
    def test_the_fixture_gives_one_build_task_per_task_in_order(self, cake_repo, tmp_path, monkeypatch):
        out, _ = extract(cake_repo, tmp_path, monkeypatch)

        got = [(e["name"], e["path"], e["line"]) for e in out["entry_points"] if e["kind"] == "build-task"]
        assert got == [("Clean", "build.cake", 5), ("Build", "build.cake", 8), ("Test", "build.cake", 12), ("Default", "build.cake", 15)]
