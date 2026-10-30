import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import render  # noqa: E402

SHA = "a" * 40


class FakeRepo:
    """Stands in for gather.Repo: serves blobs from a dict and records which paths were read."""

    def __init__(self, blobs, dirs=()):
        self.blobs, self.dirs, self.reads = blobs, set(dirs), []

    def read(self, spec):
        path = spec.split(":", 1)[1]
        self.reads.append(path)
        if path in self.blobs:
            return "blob", self.blobs[path]
        return ("tree", b"") if path.rstrip("/") in self.dirs else None


@pytest.fixture
def make_cites():
    def build(blobs, dirs=(), secret_signals=None):
        facts = {"repo": {"sha": SHA, "path": "/repo", "remote": None}}
        if secret_signals:
            facts["secret_signals"] = secret_signals
        cites = render.Cites(facts)
        cites.repo = FakeRepo(blobs, dirs)
        return cites
    return build
