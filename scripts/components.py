"""The component model (D4): suggestions for the components catalog, and the rules that decide which component owns a file.

`component_of` is shared by `dossier candidates --catalog` and by check V4. Standard library plus `gather` and `graphs`.
"""
from __future__ import annotations

import fnmatch
import re

import gather
import graphs


# A `]` may sit inside the path (a Next.js `[id]` folder); `]]` ends the citation.
CITED_PATH = re.compile(r"\[\[((?:(?!\]\]).)+?)(?::[\d\-]+)?(?:\|[^\]]*)?\]\]")


def parse_paths(cell: str) -> list:
    """['src/app/', 'scripts/*.sh'] from a `Paths` cell such as "`src/app/`, `scripts/*.sh`".
    Entries are split on commas and newlines; backticks are dropped, and a `[[path:lines|label]]` citation becomes its path."""
    found = []
    for part in re.split(r"[,\n]+", cell or ""):
        part = part.strip().strip("`").strip()
        m = CITED_PATH.fullmatch(part)
        part = m.group(1) if m else part
        if part:
            found.append(part)
    return found


def match_score(path: str, pattern: str):
    """How specifically `pattern` names `path`: None, or a sortable score. A literal file beats a glob, a glob beats a
    directory, and a deeper directory beats a shallower one."""
    if pattern == path:
        return (3, len(pattern))
    folder = pattern.rstrip("/")
    directory = (1, folder.count("/") + 1) if folder and path.startswith(folder + "/") else None
    if any(c in pattern for c in "*?["):
        # `[` may be a character class (`src/[ab].py`) or part of a folder name (`apps/a/[id]/`): try both.
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern.replace("[", "[[]")):
            return (2, len(pattern))
        return directory
    return directory


def component_of(path: str, rows: list) -> tuple:
    """(component name or None, names of other components that match equally well). `rows`: [{"name", "paths": [...]}]."""
    best, owners = None, set()
    for row in rows:
        scores = [s for s in (match_score(path, p) for p in row["paths"]) if s]
        if not scores:
            continue
        top = max(scores)
        if best is None or top > best:
            best, owners = top, {row["name"]}
        elif top == best:
            owners.add(row["name"])
    first = sorted(owners)[0] if owners else None
    return first, sorted(owners - {first}) if first else []


def catalog_rows(report: dict) -> list:
    """[{"name", "paths"}] from the `components.catalog` card of a components report."""
    rows = []
    for entry in (report or {}).get("cards", []):
        if entry.get("card") == "components.catalog":
            for block in entry.get("blocks", []):
                for row in block.get("rows", []) if isinstance(block, dict) else []:
                    cells = row.get("cells", [])
                    if len(cells) > 1:
                        rows.append({"name": cells[0].strip("`").strip(), "paths": parse_paths(cells[1])})
    return rows


def catalog_edges(rows: list, extract: dict) -> list:
    """Imports between the drafted components: [{"from", "to", "imports"}]."""
    counts: dict = {}
    for g in extract.get("graph", []):
        if g.get("kind") != "import" or not g.get("paths"):
            continue
        a, b = component_of(g["path"], rows)[0], component_of(g["paths"][0], rows)[0]
        if a and b and a != b:
            counts[(a, b)] = counts.get((a, b), 0) + 1
    return [{"from": a, "to": b, "imports": n} for (a, b), n in sorted(counts.items())]


def chunk_lines(chunks: dict) -> dict:
    """Path -> line count, from chunks.json (a file split in segments is summed)."""
    lines: dict = {}
    for chunk in (chunks or {}).get("chunks", []):
        for f in chunk.get("files", []):
            lines[f["path"]] = lines.get(f["path"], 0) + (f.get("lines") or 0)
    return lines


def file_lines(facts: dict) -> dict:
    """Path -> line count: `facts["file_lines"]` (filled from chunks.json when the dossier is loaded), else the chunks held in `facts`."""
    if (facts or {}).get("file_lines"):
        return facts["file_lines"]
    lines: dict = {}
    for chunk in ((facts or {}).get("chunks") or {}).get("chunks", []):
        for f in chunk.get("files", []):
            lines[f["path"]] = lines.get(f["path"], 0) + (f.get("lines") or 0)
    return lines


def source_files(tree, extract: dict) -> list:
    paths = tree if tree else {i["path"] for items in extract.values() for i in items}
    return sorted(p for p in paths if (gather.lang_of(p) or (None, None))[1] == "code" and not gather.noise_reason(p))


def _package_row(package: str, modules: list) -> dict:
    """A Python package with its module count; a package of a nested project also names that project's folder."""
    inside = [m for m in modules if m["module"] == package or m["module"].startswith(package + ".")]
    row = {"package": package, "modules": len(inside)}
    nested = sorted({m["project"] for m in inside if m.get("project")})
    if nested:
        row["project"] = nested[0]
    return row


def component_candidates(tree, extract: dict, facts: dict) -> dict:
    """Folders, packages and import communities, as suggestions for the components catalog. Never written to a report."""
    lines, files = file_lines(facts), source_files(tree, extract)
    folders: dict = {}
    for p in files:
        d = p.rsplit("/", 1)[0] if "/" in p else ""
        entry = folders.setdefault(d, {"path": d or ".", "files": 0, "lines": 0})
        entry["files"] += 1
        entry["lines"] += lines.get(p, 0)
    modules = [g for g in extract.get("graph", []) if g.get("kind") == "module"]
    packages = sorted({(m["module"] if m["is_package"] else m["module"].rsplit(".", 1)[0]) for m in modules if m.get("package")})
    top = {m["package"] for m in modules if m.get("package")}
    keep = [p for p in packages if p in top or p.count(".") <= 2]
    imports = [(g["from"], g["to"]) for g in extract.get("graph", []) if g.get("kind") == "import"]
    labels = graphs.communities([m["module"] for m in modules], imports)
    path_of = {m["module"]: m["path"] for m in modules}
    groups: dict = {}
    for mod, label in sorted(labels.items()):
        groups.setdefault(label, set()).add(path_of[mod].rsplit("/", 1)[0] if "/" in path_of[mod] else ".")
    out = {"folders": [folders[k] for k in sorted(folders)],
           "packages": [_package_row(p, modules) for p in keep],
           "communities": [{"label": k, "folders": sorted(v)} for k, v in sorted(groups.items()) if len(v) > 0]}
    roots = sorted({g["root"] for g in extract.get("graph", []) if g.get("kind") == "source-root" and g.get("root") and not g["path"].endswith(".csproj")})
    if roots:  # JavaScript and TypeScript projects; Python-only repositories have none, so their result is unchanged
        out["projects"] = [{"root": r, "modules": sum(1 for m in modules if m["path"].startswith(r + "/"))} for r in roots]
    return out
