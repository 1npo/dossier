"""Runs the C# adapter against a fixture repository with a fake scip-dotnet; shared by the C# adapter tests."""
import subprocess
from pathlib import Path
from types import SimpleNamespace

import scip_fake
from dossier.adapters.csharp import adapter as cs_adapter
from dossier.tooling import dotnet_sdk as cs_sdk


class FakeTS:
    def query(self, language, paths, query):
        return []


class FakeSemgrep:
    def scan(self, config, paths=None, timeout=30):
        return []


def context(cs_repo, tmp_path, trusted=True):
    root = cs_repo.path
    tree = frozenset(subprocess.run(["git", "-C", root, "ls-files"], capture_output=True, text=True).stdout.split())
    files = sorted(p for p in tree if p.endswith(".cs"))
    return SimpleNamespace(checkout=Path(root), sha=cs_repo.sha, tree=tree, files=files, area=tmp_path / "area",
                           restored={}, run=None, treesitter=FakeTS(), semgrep=FakeSemgrep(), tool_versions={}, trusted=trusted,
                           repo_name="csrepo", tool_status={}, details={})


def extract(cs_repo, tmp_path, monkeypatch, trusted=True, sdks=("10.0.403",), plan=None):
    monkeypatch.setattr(cs_sdk, "list_sdks", lambda path=None: list(sdks))
    scip_fake.install(monkeypatch, plan or {})
    ctx = context(cs_repo, tmp_path, trusted)
    return cs_adapter.CSharpAdapter().extract(ctx), ctx
