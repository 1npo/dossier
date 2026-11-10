"""scip-dotnet for the C# adapter: install it from a hash-checked NuGet package (plan 011, D3).

No `dotnet tool install` and no NuGet feed at run time. The one network call made in-process is the package download,
which checks a pinned SHA-512 before anything is unpacked. Nothing from the package is run here.
"""
import base64
import hashlib
import re
import urllib.request
import zipfile
from pathlib import Path

import cs_api
import scip_read
from shared_tools import ToolError

SUPPORTED_MAJORS = (10, 9, 8)


def install_dir(cache_root, version: str) -> Path:
    return Path(cache_root) / ".dossier-tools" / "dotnet" / f"scip-dotnet-{version}"


def _download(url: str, dest: Path, timeout: float) -> None:
    with urllib.request.urlopen(url, timeout=timeout) as resp, open(dest, "wb") as out:
        while chunk := resp.read(1 << 20):
            out.write(chunk)


def _digest(path: Path) -> str:
    h = hashlib.sha512()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return base64.b64encode(h.digest()).decode()


def _unpack(package: Path, folder: Path) -> None:
    root = folder.resolve()
    with zipfile.ZipFile(package) as z:
        for name in z.namelist():
            target = (root / name).resolve()
            if name.startswith(("/", "\\")) or ".." in Path(name).parts or root not in target.parents and target != root:
                raise ToolError("The scip-dotnet package holds a file outside its own folder, so it was not used.")
        z.extractall(root)


def ensure_installed(cache_root, tool: dict, timeout: float, fetch=None) -> Path:
    folder = install_dir(cache_root, tool["version"])
    want = tool["nupkg"]["sha512"]
    marker = folder / ".installed"
    if marker.exists() and marker.read_text().strip() == want and any(folder.glob("tools/net*/any/scip-dotnet.dll")):
        return folder
    folder.parent.mkdir(parents=True, exist_ok=True)
    part = folder.parent / f"scip-dotnet.{tool['version']}.nupkg.part"
    try:
        (fetch or _download)(tool["nupkg"]["url"], part, timeout)
        if _digest(part) != want:
            raise ToolError("The scip-dotnet package did not match its pinned checksum, so it was not used.")
        _unpack(part, folder)
        marker.write_text(want + "\n")
    except Exception:
        _remove(folder)
        raise
    finally:
        part.unlink(missing_ok=True)
    return folder


def _remove(folder: Path) -> None:
    if not folder.exists():
        return
    for p in sorted(folder.rglob("*"), reverse=True):
        p.unlink() if p.is_file() or p.is_symlink() else p.rmdir()
    folder.rmdir()


def tool_dll(folder, runtime_majors) -> Path | None:
    for major in SUPPORTED_MAJORS:
        if major in runtime_majors:
            dll = Path(folder) / "tools" / f"net{major}.0" / "any" / "scip-dotnet.dll"
            if dll.exists():
                return dll
    return None


KIND_TYPE = {"method": "method", "constructor": "method", "property": "variable", "field": "variable", "event": "variable", "enum-member": "variable"}


def _text(path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


class ScipDotnet:
    """Runs scip-dotnet on one solution or project and writes the index outside the checkout (D11)."""

    def __init__(self, run, dll, timeout: float):
        self.run, self.dll, self.timeout = run, str(dll), timeout

    def index(self, checkout, target: str, area, n: int) -> tuple:
        """(index path, exit code or None on timeout, the log: stdout then stderr). The caller decides whether it counts as a failure."""
        out = Path(area) / "scip"
        out.mkdir(parents=True, exist_ok=True)
        dest = out / f"cs-{n}.scip"
        dest.unlink(missing_ok=True)
        cmd = ["dotnet", self.dll, "index", target, "--working-directory", str(checkout), "--output", str(dest), "--skip-dotnet-restore"]
        r = self.run(cmd, cwd=Path(checkout), stage="cs-scip", profile="restricted", timeout=self.timeout)
        return dest, r.returncode, _text(r.stdout) + "\n" + _text(r.stderr)


def _lines(log: str) -> list:
    return [line.strip() for line in log.splitlines() if line.strip()]


def soft_failure(log: str) -> str | None:
    """The first `Failure:` line of the log without its label, or None. scip-dotnet exits 0 after these, with the projects it could load."""
    for line in _lines(log):
        if line.startswith("Failure:"):
            return line[len("Failure:"):].strip()
    return None


def unloaded_projects(log: str, checkout) -> set:
    """Project files (relative to the checkout) that MSBuild could not load, from `Msbuild failed when processing the file '<path>'`.

    scip-dotnet logs these after a timestamp and a level, so they are not `Failure:` lines at the start; the run still gives an index for the rest."""
    root = str(checkout).rstrip("/") + "/"
    found = set()
    for m in re.finditer(r"Msbuild failed when processing the file '([^']+)'", log):
        found.add(m.group(1)[len(root):] if m.group(1).startswith(root) else m.group(1))
    return found


def failure(returncode, log: str, index_path) -> str | None:
    """Why a run produced nothing usable (D11), or None. A run that exits 0 with `Failure:` lines is not a failure here; see `soft_failure`."""
    if returncode is None:
        return "scip-dotnet took too long and was stopped."
    if returncode != 0:
        lines = _lines(log)
        return next((line for line in lines if line.startswith("Failure:")), lines[-1] if lines else f"scip-dotnet stopped with exit code {returncode}.")
    path = Path(index_path)
    if not path.is_file() or path.stat().st_size == 0:
        return "scip-dotnet finished without writing an index."
    return None


def join(indexes: list, tree=None) -> dict:
    """One index from several. A path seen twice keeps its first document. With `tree`, documents for untracked files (obj/, bin/) are dropped."""
    seen, docs = set(), []
    for index in indexes:
        for d in index["documents"]:
            if d["path"] in seen or (tree is not None and d["path"] not in tree):
                continue
            seen.add(d["path"])
            docs.append(d)
    return {"documents": docs}


def _type_name(symbol: str) -> str | None:
    names = [name for name, suffix in scip_read.descriptors(symbol) if suffix == "#"]
    return names[-1] if names else None


def disambiguate(index: dict, decls: dict) -> tuple:
    """scip-dotnet keeps only the last namespace segment, so two types can share a symbol. A symbol defined in two files is kept when every
    one of them declares a `partial` type of that name; otherwise all its occurrences become `local ambiguous-N`, which `reduce` skips."""
    defined: dict = {}
    for d in index["documents"]:
        for o in d["occurrences"]:
            if o["roles"] & scip_read.DEFINITION and not o["symbol"].startswith("local "):
                defined.setdefault(o["symbol"], set()).add(d["path"])
    partial = {path: {t["name"] for t in f.get("types", ()) if t.get("partial")} for path, f in decls.items()}
    renamed: dict = {}
    for symbol, paths in sorted(defined.items()):
        name = _type_name(symbol)
        if len(paths) > 1 and not (name and all(name in partial.get(p, ()) for p in paths)):
            renamed[symbol] = f"local ambiguous-{len(renamed)}"
    if not renamed:
        return index, 0
    docs = [{**d, "occurrences": [{**o, "symbol": renamed.get(o["symbol"], o["symbol"])} for o in d["occurrences"]],
             "symbols": [{**s, "symbol": renamed.get(s["symbol"], s["symbol"])} for s in d["symbols"]]} for d in index["documents"]]
    return {"documents": docs}, len(renamed)


def _flag(flags: list, name: str, line: int) -> bool:
    inside = [f for f in flags if f[1] <= line <= f[2]]
    named = [f for f in inside if f[0] == name] or inside
    return min(named, key=lambda f: f[2] - f[1])[3] if named else False


def finish_symbols(items: list, decls: dict, generated) -> list:
    """Drop parameter and type-parameter definitions and definitions in generated files; set `public` from the declarations (D15)."""
    parts = cs_api.partial_parts({p: d for p, d in decls.items() if p not in generated})
    flags: dict = {}
    out = []
    for it in items:
        if it["kind"] == "def":
            if it["symbol"].endswith((")", "]")) or it["path"] in generated:
                continue
            if it["path"] not in flags:
                flags[it["path"]] = cs_api.line_flags(decls[it["path"]], parts) if it["path"] in decls else []
            it = {**it, "public": _flag(flags[it["path"]], it["name"], it["line"])}
        out.append(it)
    return out


def fallback_defs(decls: dict, generated) -> list:
    """One `def` per declaration when scip-dotnet did not run. Symbols carry no line number, so the digest is stable between such builds."""
    live = {p: d for p, d in decls.items() if p not in generated}
    parts = cs_api.partial_parts(live)
    out, seen = [], set()
    for path in sorted(live):
        by_name = {t["name"]: t for t in live[path]["types"]}
        for t in live[path]["types"]:
            chain = cs_api.chain(t, by_name)
            dotted = ".".join([o["name"] for o in chain] + [t["name"]])
            base = f"cs {t.get('namespace') or ''}/{dotted}#"
            same = parts.get(cs_api.key(t, by_name), [])
            rows = [(base, t["name"], "class", t, chain)] + [(base + m["name"], m["name"], KIND_TYPE.get(m["kind"], "variable"), m, chain + [t]) for m in t["members"]]
            for symbol, name, kind, decl, outers in rows:
                if symbol in seen:
                    continue
                seen.add(symbol)
                out.append({"kind": "def", "path": path, "line": decl["line"], "end_line": decl["end_line"], "name": name, "symbol": symbol, "type": kind,
                            "public": cs_api.is_public(decl, outers, same), "refs": 0, "via": "tree-sitter"})
    return out


DYNAMIC_USE = {"di-registration", "di-scan", "mediator-handler", "mvc-filter", "route-convention", "reflection"}
UNUSED = "Nothing in the repository references this type."


def _base_name(base: str) -> str:
    return base.split("<", 1)[0].rsplit(".", 1)[-1].strip()


def drop_unrelated(items: list, projects: list, project_of: dict) -> tuple:
    """(items, dropped): `ref-edge` items between files of two projects that do not reach each other through project references are removed.

    scip-dotnet keeps only the last namespace segment, so every top-level `Program` shares one symbol and links unrelated projects."""
    refs = {p["path"]: p.get("references", []) for p in projects}
    reach: dict = {}
    for start in refs:
        seen, todo = set(), [start]
        while todo:
            q = todo.pop()
            if q not in seen:
                seen.add(q)
                todo.extend(refs.get(q, ()))
        reach[start] = seen
    kept, dropped = [], 0
    for it in items:
        if it.get("kind") == "ref-edge":
            a, b = project_of.get(it["path"]), project_of.get((it.get("paths") or [""])[0])
            if a and b and a != b and b not in reach.get(a, ()) and a not in reach.get(b, ()):
                dropped += 1
                continue
        kept.append(it)
    return kept, dropped


def dead_items(symbols: list, decls: dict, entries: list, models: list, blindspots: list, generated, test_files, unloaded=()) -> list:
    """`dead` items for internal types that no other file references (D17). Run only when scip-dotnet gave an index.

    `refs` counts uses from other files, so a name used again inside its own file also keeps a type off the list.
    `unloaded` holds project files the indexer could not load: calls made from there never resolved, so a type in them cannot be called dead."""
    skip = tuple(u.rsplit("/", 1)[0] + "/" if "/" in u else "" for u in unloaded)
    defs = {(s["path"], s["name"]): s for s in symbols if s["kind"] == "def" and s["symbol"].endswith("#")}
    used_members = [(s["path"], s["line"]) for s in symbols if s["kind"] == "def" and not s["symbol"].endswith("#") and s["refs"]]
    dynamic = {b["path"] for b in blindspots if b.get("pattern") in DYNAMIC_USE}
    entities = {(m["path"], m["name"]) for m in models}
    declared = {t["name"] for d in decls.values() for t in d["types"]}
    rows = []
    for path, d in sorted(decls.items()):
        if path in generated or path in test_files or path in dynamic:
            continue
        if skip and any(path.startswith(k) for k in skip):  # the project did not load, so its references are missing
            continue
        for t in d["types"]:
            found = defs.get((path, t["name"]))
            if (t["kind"] not in ("class", "record", "struct") or found is None or found["public"] or found["refs"] or (path, t["name"]) in entities
                    or not t["line"] <= found["line"] <= t["end_line"]):
                continue
            if any(t["line"] <= e["line"] <= t["end_line"] for e in entries if e["path"] == path and e.get("line")):
                continue
            if any(p == path and t["line"] <= ln <= t["end_line"] for p, ln in used_members):  # x.AddAspire() references the method, not its class
                continue
            if any(_base_name(b) not in declared for b in t["bases"]):
                continue
            if any(not t["line"] <= ln <= t["end_line"] for ln in d.get("idents", {}).get(t["name"], ())):
                continue
            rows.append({"path": path, "line": t["line"], "end_line": t["end_line"], "type": "dead code without references", "name": t["name"],
                         "message": UNUSED, "confidence": None, "rule": "scip-dotnet.unused-type", "snippet": UNUSED})
    return rows
