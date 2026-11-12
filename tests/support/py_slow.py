import json
"""The extraction harness of the Python adapter's slow tests, shared with the tests that reuse it."""
from dossier.core import buildlog
from dossier.pipeline import stages
from dossier.pipeline import workarea


class Extracted:
    def __init__(self, tmp_path, py_repo):
        self.repo, self.tmp = py_repo, tmp_path
        self.top, self.sha = py_repo.path, py_repo.sha
        self.out = tmp_path / "home" / "pyrepo"
        self.area = workarea.area_for("pyrepo", self.top, self.sha, tmp_path / "cache")
        self.checkout = workarea.ensure_checkout(self.area, self.top, self.sha)["path"]
        self.tree = stages.tree_at(self.top, self.sha)
        self.build = buildlog.start(self.out, repo="pyrepo", sha=self.sha, ref="main", version="test", options={})

    def run(self):
        return stages.stage_extract(self.build, self.top, self.sha, self.area, self.out, ["Python", "Shell", "YAML"],
                                    workarea.trusted(self.top, self.sha), stages.Options(), {}, self.tree, self.checkout)

    def items(self, output):
        data = json.loads((self.out / "extract" / f"{output}.json").read_text())
        return [i for name in sorted(data["adapters"]) for i in data["adapters"][name]["items"]]

    def line(self, rel, name):
        return self.repo.line_of(rel, name)
