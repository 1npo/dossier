"""Upgrade burden (D3): how far the runtime and the main frameworks are from end of life, from a shipped snapshot.

The snapshot is `src/dossier/data/eol.json`, refreshed by hand with tools/refresh_eol.py. The .NET list is fetched once, by `prepare`, and pinned in `refdata.json` beside the facts (`render --refresh-refdata` fetches it again). Products the source does not know
(flask, fastapi, sqlalchemy, pydantic) are simply not listed.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dossier.render.measured import change as measured_change
from dossier import resources
from dossier.render import markup

SNAPSHOT = resources.data("eol.json")
DOTNET_INDEX = "https://dotnetcli.blob.core.windows.net/dotnet/release-metadata/releases-index.json"
PACKAGE_PRODUCTS = {"django": "django", "react": "react", "next": "nextjs"}


def load_snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def dotnet_cycles_from_index(index) -> list:
    """The snapshot's `dotnet` shape from Microsoft's releases-index.json: cycle `10` for channel `10.0` (`3.1` stays), newest first."""
    out = []
    for r in (index or {}).get("releases-index") or []:
        channel = str(r.get("channel-version") or "")
        m = re.fullmatch(r"(\d+)\.(\d+)", channel)
        if not m or not r.get("latest-release"):
            continue
        cycle = m.group(1) if m.group(2) == "0" and int(m.group(1)) >= 5 else channel
        out.append({"cycle": cycle, "eol": r.get("eol-date") or None, "latest": r["latest-release"], "_k": (int(m.group(1)), int(m.group(2)))})
    out.sort(key=lambda c: c["_k"], reverse=True)
    for c in out:
        del c["_k"]
    return out


def fetch_dotnet_index(timeout=5):
    """Microsoft's releases-index.json parsed, or None with no network, a bad status or bad JSON. Off when DOSSIER_OFFLINE is set."""
    if os.environ.get("DOSSIER_OFFLINE"):
        return None
    try:
        with urllib.request.urlopen(DOTNET_INDEX, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError):
        return None


def fetch_refdata(fetch=None, today=None) -> dict:
    """What the build pins: {"dotnet": {"fetched": date, "cycles": [...]}} from the live index, or {} when it cannot be read."""
    cycles = dotnet_cycles_from_index((fetch or fetch_dotnet_index)())
    if not cycles:
        return {}
    return {"dotnet": {"fetched": today or datetime.now(timezone.utc).strftime("%Y-%m-%d"), "cycles": cycles}}


def resolve_snapshot(refdata=None):
    """(snapshot, note on where the .NET data came from). The pinned fetch in `refdata` replaces the snapshot's `dotnet` list; nothing is read from the network here, so a render is a function of the build."""
    snap = load_snapshot()
    pinned = (refdata or {}).get("dotnet") or {}
    if pinned.get("cycles"):
        return {**snap, "products": {**snap["products"], "dotnet": pinned["cycles"]}}, f"from Microsoft's releases-index.json, fetched {pinned['fetched']}"
    return snap, f"from the offline snapshot of {snap['as_of']} (no fetch of Microsoft's releases-index.json is pinned in this build; run render with --refresh-refdata)"


def _cycle(text):
    m = re.search(r"(\d+)\.(\d+)", text or "")
    return f"{m.group(1)}.{m.group(2)}" if m else None


def _major(text):
    m = re.search(r"\d+", text or "")
    return m.group(0) if m else None


def _cycle_of(product):
    """Django's cycles are `5.2`; those of Node, React and Next are a major number."""
    return _cycle if product == "django" else _major


def _node_pin(ctx):
    """(pinned text, source path) from `.nvmrc`, `.node-version`, then `engines.node` of the first package.json, or (None, None)."""
    read, tree = ctx.get("read"), sorted(ctx.get("tree") or ())
    if read is None:
        return None, None
    for name in (".nvmrc", ".node-version"):
        text = (read(name) or "").strip() if name in tree else ""
        if text and _major(text.splitlines()[0]):
            return text.splitlines()[0], name
    manifests = sorted((p for p in tree if p.rsplit("/", 1)[-1] == "package.json"), key=lambda p: (p.count("/"), p))
    if manifests:
        try:
            engines = (json.loads(read(manifests[0]) or "{}").get("engines") or {}).get("node")
        except (ValueError, AttributeError):
            engines = None
        if isinstance(engines, str) and _major(engines):
            return f"engines.node {engines}", manifests[0]
    return None, None


DOTNET_FRAMEWORK = re.compile(r"^(?:net(\d+)\.0(?:-[\w.]+)?|netcoreapp(3\.1))$")


def _dotnet_rows(ctx, snap, today) -> list:
    """One row per distinct target framework of the non-test C# projects (D19), naming the first project (by path) that sets it."""
    if "dotnet" not in snap["products"]:
        return []
    cycles = snap["products"]["dotnet"]
    first: dict = {}
    for g in sorted((g for g in (ctx.get("extract") or {}).get("graph", []) if g.get("kind") == "cs-project" and not g.get("test")), key=lambda g: g["path"]):
        for framework in g.get("frameworks") or []:
            first.setdefault(framework, g["path"])
    out = []
    for framework, path in sorted(first.items(), key=lambda kv: (kv[1], kv[0])):
        m = DOTNET_FRAMEWORK.match(framework)
        if m:
            gap, _ = _gap(cycles, m.group(1) or m.group(2), today)
            out.append((".NET", f"TargetFramework {framework}", f"{cycles[0]['latest']} (latest)", gap, path))
    return out


def _gap(cycles, cycle, today):
    entry = next((c for c in cycles if c["cycle"] == cycle), None)
    if not entry or not entry.get("eol"):
        return "not in the data", entry
    return (f"end of life since {entry['eol']}" if entry["eol"] <= today else f"supported until {entry['eol']}"), entry


def rows(ctx, snapshot=None):
    """[(name, pinned, latest, gap, source path or None)]."""
    facts, read = ctx.get("facts") or {}, ctx.get("read")
    snap = snapshot or resolve_snapshot(facts.get("refdata"))[0]
    today = (facts.get("repo") or {}).get("commit_date") or snap["as_of"]
    out = []
    pinned, source = None, None
    version_file = read(".python-version") if read else None
    manifests = facts.get("manifests") or []
    if version_file and _cycle(version_file):
        pinned, source = version_file.strip().splitlines()[0], ".python-version"
    else:
        for m in manifests:
            req = (m.get("extra") or {}).get("requires-python")
            if req and _cycle(req):
                pinned, source = f"requires-python {req}", m["path"]
                break
    if pinned and "python" in snap["products"]:
        cycles = snap["products"]["python"]
        gap, _ = _gap(cycles, _cycle(pinned), today)
        newest = cycles[0]
        out.append(("Python", pinned, f"{newest['latest']} (latest)", gap, source))
    node, node_source = _node_pin(ctx)
    if node and "nodejs" in snap["products"]:
        cycles = snap["products"]["nodejs"]
        gap, _ = _gap(cycles, _major(node), today)
        out.append(("Node.js", node, f"{cycles[0]['latest']} (latest)", gap, node_source))
    out += _dotnet_rows(ctx, snap, today)
    deps = (facts.get("dependencies") or {}).get("deps") or []
    seen = set()
    for d in sorted(deps, key=lambda d: d["n"]):
        product = PACKAGE_PRODUCTS.get(d["n"].lower())
        cycle = _cycle_of(product)(d.get("v")) if product else None
        if not product or product not in snap["products"] or not cycle or (d["n"], d.get("v")) in seen:
            continue
        seen.add((d["n"], d.get("v")))
        cycles = snap["products"][product]
        gap, _ = _gap(cycles, cycle, today)
        src = next((m["path"] for m in manifests if any(x.get("name", "").lower() == d["n"].lower() for x in m["dependencies"])), None)
        out.append((d["n"], d["v"], f"{cycles[0]['latest']} (latest)", gap, src))
    return out


def card(cid, ctx, refs):
    if not measured_change.has_history(ctx) and not (ctx.get("facts") or {}).get("manifests"):
        return None
    snap, dotnet_note = resolve_snapshot((ctx.get("facts") or {}).get("refdata"))
    found = rows(ctx, snap)
    text = f"Data as of {snap['as_of']}, from endoflife.date."
    if any(r[0] == ".NET" for r in found):
        text += f" .NET {dotnet_note}."
    caption = measured_change.foot_notes(text)
    if not found:
        return measured_change.none_found("No runtime or package with end-of-life data was found.") + caption
    cells = [[markup.E(n), markup.E(p), markup.E(l), markup.E(g), markup.source_cell(refs, (s, None)) if s else ""] for n, p, l, g, s in found]
    return markup.render_table(["Runtime or package", "Pinned", "Latest or supported", "Gap", "Source"], cells, refs, "t-change-upgrade-burden", plain=True) + caption


DRAWN = {"change.upgrade-burden": card}
