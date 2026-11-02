"""What the Python adapter reads from project files: package roots, console scripts, import rules, test settings.

Pure functions over a checkout folder and the set of tracked paths. Standard library only. Missing or unparsable
files give empty results; they never raise.
"""
from __future__ import annotations

import configparser
import re
import tomllib
from pathlib import Path

import gather

CONTRACT_KEYS = ("layers", "containers", "source_modules", "forbidden_modules", "modules", "ignore_imports")


def read_blob(checkout, rel: str):
    """Text of a file in the checkout, or None when it is absent or not text."""
    try:
        return (Path(checkout) / rel).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _toml(checkout, rel: str):
    text = read_blob(checkout, rel)
    if text is None:
        return {}
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return {}


def _ini(checkout, rel: str):
    text = read_blob(checkout, rel)
    if text is None:
        return None
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        parser.read_string(text)
    except configparser.Error:
        return None
    return parser


def _lines(value) -> list:
    if isinstance(value, list):
        return [str(v) for v in value]
    return [v.strip() for v in str(value).splitlines() if v.strip()]


def _find_line(text, pattern: str) -> int:
    """1-based line of the first line matching the regular expression, or 1."""
    for i, line in enumerate((text or "").splitlines(), 1):
        if re.search(pattern, line):
            return i
    return 1


# ------------------------------------------------------------------ package roots


def _configured_packages(checkout) -> list:
    """(root, package) pairs named in the build configuration."""
    data = _toml(checkout, "pyproject.toml")
    found = []
    wheel = data.get("tool", {}).get("hatch", {}).get("build", {}).get("targets", {}).get("wheel", {})
    for p in wheel.get("packages", []):
        root, _, pkg = str(p).rpartition("/")
        found.append((root, pkg))
    st = data.get("tool", {}).get("setuptools", {})
    root = st.get("package-dir", {}).get("", "")
    for pkg in st.get("packages", []) if isinstance(st.get("packages"), list) else []:
        found.append((str(root).strip("/"), str(pkg).split(".")[0]))
    for entry in data.get("tool", {}).get("poetry", {}).get("packages", []):
        if isinstance(entry, dict) and "include" in entry:
            found.append((str(entry.get("from", "")).strip("/"), str(entry["include"]).split("/")[0]))
    return found


def package_roots(tree, checkout) -> list:
    """[{"root": "src", "package": "shopcart"}]: top-level packages, tests and noise left out."""
    roots = {""} | {r for r, _ in _configured_packages(checkout)} | {"src"}
    found = set()
    for path in tree:
        if not path.endswith("/__init__.py"):
            continue
        pkg_dir = path[: -len("/__init__.py")]
        root, _, name = pkg_dir.rpartition("/")
        if root not in roots or gather.TEST_RE.search(pkg_dir + "/") or gather.noise_reason(path):
            continue
        found.add((root, name))
    for root, pkg in _configured_packages(checkout):
        if (root + "/" + pkg if root else pkg) + "/__init__.py" in tree:
            found.add((root, pkg))
    return [{"root": r, "package": p} for r, p in sorted(found)]


def loose_modules(tree, roots) -> list:
    """Tracked .py files that are outside every package (tests and noise left out)."""
    prefixes = tuple((r + "/" if r else "") + p + "/" for r, p in ((x["root"], x["package"]) for x in roots))
    return sorted(p for p in tree if p.endswith(".py") and not p.startswith(prefixes)
                  and not gather.TEST_RE.search(p) and not gather.noise_reason(p))


# ------------------------------------------------------------------ console scripts


def console_scripts(checkout) -> list:
    text = read_blob(checkout, "pyproject.toml")
    data = _toml(checkout, "pyproject.toml")
    project = data.get("project", {})
    groups = {"scripts": project.get("scripts", {}), "gui-scripts": project.get("gui-scripts", {})}
    for group, table in project.get("entry-points", {}).items():
        groups[group] = table
    groups.setdefault("scripts", {}).update(data.get("tool", {}).get("poetry", {}).get("scripts", {}))
    found = []
    for group, table in groups.items():
        for name, target in table.items():
            found.append({"name": name, "target": str(target), "line": _find_line(text, r"^\s*\"?" + re.escape(name) + r"\"?\s*="),
                          "path": "pyproject.toml", "group": group})
    cfg = _ini(checkout, "setup.cfg")
    if cfg and cfg.has_option("options.entry_points", "console_scripts"):
        cfg_text = read_blob(checkout, "setup.cfg")
        for entry in _lines(cfg.get("options.entry_points", "console_scripts")):
            name, _, target = entry.partition("=")
            found.append({"name": name.strip(), "target": target.strip(),
                          "line": _find_line(cfg_text, r"^\s*" + re.escape(name.strip()) + r"\s*="),
                          "path": "setup.cfg", "group": "scripts"})
    return sorted(found, key=lambda s: (s["path"], s["group"], s["name"]))


# ------------------------------------------------------------------ import-linter contracts


def _contract(raw: dict, text, path: str) -> dict:
    name = str(raw.get("name", raw.get("id", "")))
    item = {"name": name, "type": str(raw.get("type", "")), "path": path,
            "line": _find_line(text, r"\bname\s*[=:]\s*[\"']?" + re.escape(name)) if name else 1}
    for key in CONTRACT_KEYS:
        if key in raw:
            item[key] = _lines(raw[key])
    return item


def _ini_contracts(checkout, rel: str, header: str) -> dict | None:
    cfg = _ini(checkout, rel)
    if cfg is None:
        return None
    text = read_blob(checkout, rel)
    main = header if cfg.has_section(header) else None
    if main is None and not any(s.startswith(header + ":contract:") for s in cfg.sections()):
        return None
    root = dict(cfg[main]) if main else {}
    roots = _lines(root.get("root_packages", "")) or _lines(root.get("root_package", ""))
    contracts = [_contract(dict(cfg[s]) | {"id": s.rsplit(":", 1)[-1]}, text, rel)
                 for s in cfg.sections() if s.startswith(header + ":contract:")]
    return {"path": rel, "root_packages": roots, "contracts": contracts}


def importlinter_contracts(checkout) -> dict:
    """{"path", "root_packages", "contracts"} from .importlinter, setup.cfg or pyproject.toml; "error" if unparsable."""
    empty = {"path": None, "root_packages": [], "contracts": []}
    error = None
    for rel, header in ((".importlinter", "importlinter"), ("setup.cfg", "importlinter")):
        if read_blob(checkout, rel) is None:
            continue
        got = _ini_contracts(checkout, rel, header)
        if got:
            return got
        if _ini(checkout, rel) is None:
            error = f"{rel} could not be read"
    text = read_blob(checkout, "pyproject.toml")
    if text is not None:
        try:
            cfg = tomllib.loads(text).get("tool", {}).get("importlinter")
        except tomllib.TOMLDecodeError as e:
            error = f"pyproject.toml could not be read: {e}"
            cfg = None
        if cfg:
            roots = _lines(cfg.get("root_packages", [])) or _lines(cfg.get("root_package", ""))
            return {"path": "pyproject.toml", "root_packages": roots,
                    "contracts": [_contract(c, text, "pyproject.toml") for c in cfg.get("contracts", [])]}
    return {**empty, "error": error} if error else empty


# ------------------------------------------------------------------ vulture and test settings


def vulture_config(checkout) -> dict:
    cfg = _toml(checkout, "pyproject.toml").get("tool", {}).get("vulture", {})
    return {"ignore_names": _lines(cfg.get("ignore_names", [])), "ignore_decorators": _lines(cfg.get("ignore_decorators", [])),
            "exclude": _lines(cfg.get("exclude", [])), "min_confidence": int(cfg.get("min_confidence", 60))}


def _settings(source: dict) -> dict:
    out = {}
    for key in ("fail_under", "addopts", "testpaths"):
        if key in source:
            out[key] = source[key]
    return out


def test_configs(checkout, tree) -> list:
    """D2 "config" items for pytest, coverage, tox and nox."""
    items = []
    tool = _toml(checkout, "pyproject.toml").get("tool", {})
    if "pytest" in tool and "ini_options" in tool["pytest"]:
        items.append({"kind": "config", "path": "pyproject.toml", "tool": "pytest", "settings": _settings(tool["pytest"]["ini_options"])})
    cov = tool.get("coverage", {})
    if cov:
        settings = {**_settings(cov.get("run", {})), **_settings(cov.get("report", {}))}
        items.append({"kind": "config", "path": "pyproject.toml", "tool": "coverage", "settings": settings})
    for rel, section, name in (("pytest.ini", "pytest", "pytest"), ("setup.cfg", "tool:pytest", "pytest"),
                               ("tox.ini", "pytest", "pytest"), (".coveragerc", "report", "coverage"),
                               ("setup.cfg", "coverage:report", "coverage")):
        cfg = _ini(checkout, rel)
        if cfg is not None and cfg.has_section(section):
            items.append({"kind": "config", "path": rel, "tool": name, "settings": _settings(dict(cfg[section]))})
    for rel, name in (("tox.ini", "tox"), ("noxfile.py", "nox")):
        if rel in tree:
            items.append({"kind": "config", "path": rel, "tool": name, "settings": {}})
    return sorted(items, key=lambda i: (i["path"], i["tool"]))
