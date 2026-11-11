#!/usr/bin/env python3
"""Rewrite src/dossier/data/eol.json from endoflife.date. Run by hand when the snapshot is stale; the skill never calls the network for this.

    python3 tests/tools/refresh_eol.py                 # every product, and a new as_of date
    python3 tests/tools/refresh_eol.py --add react     # only these products, added to the file; the others and as_of stay as they are
"""
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[2] / "src")]
sys.path.append(str(Path(__file__).resolve().parents[2] / "scripts"))  # TRANSITION: removed in C11

from dossier import resources  # noqa: E402

SOURCE = "https://endoflife.date/api/v1/products/"
PRODUCTS = ("python", "django", "nodejs", "dotnet", "postgresql", "react", "nextjs")
OUT = resources.data("eol.json")


def fetch(name):
    if name == "dotnet":  # Microsoft's own index, the same source the skill reads live
        from dossier.render.measured import upgrade as measured_upgrade
        with urllib.request.urlopen(measured_upgrade.DOTNET_INDEX, timeout=30) as r:
            return measured_upgrade.dotnet_cycles_from_index(json.load(r))
    with urllib.request.urlopen(SOURCE + name, timeout=30) as r:
        releases = json.load(r)["result"]["releases"]
    return [{"cycle": x["name"], "eol": x.get("eolFrom"), "latest": (x.get("latest") or {}).get("name")} for x in releases]


def add(names):
    """Fetch only `names` and merge them into the existing file, so the data of every other product (and `as_of`) is unchanged."""
    data = json.loads(OUT.read_text())
    for name in names:
        data["products"][name] = fetch(name)
    OUT.write_text(json.dumps(data, indent=1) + "\n")
    print(f"added {', '.join(names)} to {OUT}")


def main():
    if sys.argv[1:2] == ["--add"] and sys.argv[2:]:
        return add(sys.argv[2:])
    data = {"as_of": date.today().isoformat(), "source": SOURCE + " (dotnet: Microsoft releases-index.json)", "products": {p: fetch(p) for p in PRODUCTS}}
    OUT.write_text(json.dumps(data, indent=1) + "\n")
    print(f"wrote {OUT} ({sum(len(v) for v in data['products'].values())} releases)")


if __name__ == "__main__":
    main()
