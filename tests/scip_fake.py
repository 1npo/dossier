"""A fake scip-dotnet for adapter tests: encodes a small SCIP index and stands in for `cs_scip.ScipDotnet`."""
from pathlib import Path


def varint(n):
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out


def field(num, payload):
    if isinstance(payload, int):
        return varint(num << 3) + varint(payload)
    if isinstance(payload, str):
        payload = payload.encode()
    return varint((num << 3) | 2) + varint(len(payload)) + payload


def index_bytes(docs):
    """docs: {path: [(symbol, roles, line)]} -> bytes of an index. Symbols are written as `scip-dotnet nuget . . ` + the text given."""
    body = b""
    for path, occurrences in docs.items():
        doc = field(1, path)
        for symbol, roles, line in occurrences:
            rng = b"".join(varint(n) for n in (line, 0, line, 5))
            doc += field(2, field(1, rng) + field(2, "scip-dotnet nuget . . " + symbol) + field(3, roles) + field(7, b"".join(varint(n) for n in (line, 0, line + 2, 1))))
        body += field(2, doc)
    return body


class FakeScipDotnet:
    """Replaces `cs_scip.ScipDotnet`. `plan` maps a target to (exit code, log, docs or None); a target not in it gives a clean run whose one document is not tracked, so it adds nothing."""

    plan: dict = {}
    seen: list = []

    def __init__(self, run, dll, timeout):
        pass

    def index(self, checkout, target, area, n):
        FakeScipDotnet.seen.append(target)
        code, log, docs = FakeScipDotnet.plan.get(target, (0, "", {"untracked.cs": []}))
        dest = Path(area) / "scip" / f"cs-{n}.scip"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.unlink(missing_ok=True)
        if docs is not None:
            dest.write_bytes(index_bytes(docs))
        return dest, code, log


def install(monkeypatch, plan):
    """Make `cs_adapter` use the fake in place of the real download and run."""
    import cs_scip
    import cs_sdk
    FakeScipDotnet.plan, FakeScipDotnet.seen = plan, []
    monkeypatch.setattr(cs_scip, "ensure_installed", lambda cache, tool, timeout, fetch=None: Path(cache))
    monkeypatch.setattr(cs_scip, "tool_dll", lambda folder, majors: Path(folder) / "scip-dotnet.dll")
    monkeypatch.setattr(cs_scip, "ScipDotnet", FakeScipDotnet)
    monkeypatch.setattr(cs_sdk, "list_runtime_majors", lambda path=None: [10])
    return FakeScipDotnet
