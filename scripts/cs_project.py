"""C# solutions and projects, read from the text of the tracked files (plan 011, D7). Pure: no `dotnet`, no restore.

`projects(tree, read)` takes the tracked paths and a `read(path) -> str | None`. Properties come from unconditioned
`PropertyGroup`s of the project and of every `Directory.Build.props` above it; conditions are not evaluated.
"""
import posixpath
import re
import xml.etree.ElementTree as ET

import gather

TEST_PACKAGES = {"microsoft.net.test.sdk", "xunit", "xunit.v3", "nunit", "mstest.testframework", "mstest", "tunit"}
UNSUPPORTED_FRAMEWORKS = ("FastEndpoints", "Carter", "ServiceStack", "Nancy", "Wolverine", "Microsoft.Orleans.Server",
                          "Dapr.AspNetCore", "Akka", "Aspire.Hosting.AppHost")
SDK_FRAMEWORKS = {"Aspire.AppHost.Sdk": "Aspire.Hosting.AppHost"}
OTHER_LANGUAGES = {".fsproj": "F#", ".vbproj": "Visual Basic"}
SLN_RE = re.compile(r'(?m)^Project\("\{[^}]+\}"\)\s*=\s*"[^"]*",\s*"([^"]+\.csproj)"')


def _parse(text):
    root = ET.fromstring((text or "").lstrip("﻿"))
    for el in root.iter():
        el.tag = el.tag.rsplit("}", 1)[-1]
    return root


def _props(root) -> dict:
    out = {}
    for group in root.findall("PropertyGroup"):
        if group.get("Condition"):
            continue
        for el in group:
            if not el.get("Condition") and el.text and el.text.strip():
                out[el.tag] = el.text.strip()
    return out


def _dir(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else ""


def _join(base: str, rel: str) -> str:
    return posixpath.normpath(posixpath.join(base, rel.replace("\\", "/")))


def _inherited(directory: str, read, props_files: set) -> dict:
    chain, d = [], directory
    while True:
        f = f"{d}/Directory.Build.props" if d else "Directory.Build.props"
        if f in props_files:
            chain.append(f)
        if not d:
            break
        d = _dir(d)
    merged = {}
    for f in reversed(chain):
        try:
            merged.update(_props(_parse(read(f))))
        except ET.ParseError:
            continue
    return merged


def _flag(props: dict, name: str):
    v = props.get(name)
    return None if v is None else v.lower() == "true"


def _project(path: str, read, props_files: set, tracked: set) -> dict:
    base = path.rsplit("/", 1)[-1]
    name, ext = base.rsplit(".", 1)[0], "." + base.rsplit(".", 1)[-1]
    directory = _dir(path)
    out = {"path": path, "dir": directory, "name": name, "files": []}
    if ext in OTHER_LANGUAGES:
        return out | {"language": OTHER_LANGUAGES[ext], "test": False, "packable": False, "references": [], "packages": [],
                      "friends": [], "frameworks": [], "lock": False, "sdks": []}
    try:
        root = _parse(read(path))
    except ET.ParseError as e:
        return out | {"error": str(e).splitlines()[0], "sdk": None, "sdks": [], "output_type": "Library", "frameworks": [], "test": False,
                      "packable": False, "package_id": None, "assembly": name, "root_namespace": name, "references": [],
                      "packages": [], "friends": [], "lock": False}
    props = _inherited(directory, read, props_files) | _props(root)
    sdks = [n for n in (part.strip().split("/")[0] for part in (root.get("Sdk") or "").split(";")) if n]
    sdks += [el.get("Name").split("/")[0] for el in root.iter("Sdk") if el.get("Name")]
    sdk = sdks[0] if sdks else None
    web = sdk in ("Microsoft.NET.Sdk.Web", "Microsoft.NET.Sdk.Worker")
    output = props.get("OutputType") or ("Exe" if web else "Library")
    frameworks = [f for f in (props.get("TargetFrameworks") or props.get("TargetFramework") or "").split(";") if f]
    packages = [el.get("Include") for el in root.iter("PackageReference") if el.get("Include")]
    refs = [r for r in (_join(directory, el.get("Include")) for el in root.iter("ProjectReference") if el.get("Include")) if r in tracked]
    friends = [el.get("Include") for el in root.iter("InternalsVisibleTo") if el.get("Include")]
    test = bool(_flag(props, "IsTestProject")) or (sdk or "").startswith("MSTest.Sdk") or any(p.lower() in TEST_PACKAGES for p in packages)
    exe = output in ("Exe", "WinExe") and not _flag(props, "PackAsTool")
    packable = not (_flag(props, "IsPackable") is False or test or exe or web)
    assembly = props.get("AssemblyName") or name
    lock = f"{directory}/packages.lock.json" if directory else "packages.lock.json"
    return out | {"sdk": sdk, "sdks": sdks, "output_type": output, "frameworks": frameworks, "test": test, "packable": packable,
                  "package_id": (props.get("PackageId") or assembly) if packable else None, "assembly": assembly,
                  "root_namespace": props.get("RootNamespace") or name, "references": refs, "packages": packages,
                  "friends": friends, "lock": lock in tracked}


def _solution(path: str, read) -> list:
    text = read(path) or ""
    if path.endswith(".slnx"):
        try:
            found = [el.get("Path") for el in _parse(text).iter("Project") if el.get("Path")]
        except ET.ParseError:
            found = []
    else:
        found = SLN_RE.findall(text)
    return [_join(_dir(path), p) for p in found]


def projects(tree, read) -> dict:
    tracked = set(tree)
    paths = sorted(p for p in tracked if not gather.noise_reason(p) or p.endswith("proj"))
    props_files = {p for p in tracked if p.rsplit("/", 1)[-1] == "Directory.Build.props"}
    found = [_project(p, read, props_files, tracked) for p in paths if p.endswith((".csproj", *OTHER_LANGUAGES))]
    dirs = sorted({p["dir"] for p in found}, key=lambda d: -len(d))
    for p in paths:
        if not p.endswith(".cs"):
            continue
        owner = next((d for d in dirs if d == "" or p.startswith(d + "/")), None)
        match = [q for q in found if q["dir"] == owner and "language" not in q]
        if match:
            match[0]["files"].append(p)
    for q in found:
        q["files"].sort()
    solutions = [{"path": p, "projects": _solution(p, read)} for p in paths if p.endswith((".sln", ".slnx"))]
    owned = {f for q in found for f in q["files"]}
    covered = {x for s in solutions for x in s["projects"]}
    loose = [p for p in paths if p.endswith(".cs") and p not in owned]
    free = [q["path"] for q in found if q["path"].endswith(".csproj") and q["path"] not in covered]
    return {"solutions": solutions, "projects": found, "loose_files": loose,
            "targets": [s["path"] for s in solutions] + free}


def source_roots(result: dict, tree) -> list:
    cs = [p for p in result["projects"] if "language" not in p]
    items = []
    for p in cs:
        root = p["dir"] if len(cs) == 1 else _dir(p["dir"]) if p["dir"] else ""
        if root:
            items.append({"kind": "source-root", "path": p["path"], "root": root})
    return items


def project_frameworks(project: dict) -> list:
    """The unsupported frameworks one project names, by package or by SDK, in `UNSUPPORTED_FRAMEWORKS` order."""
    seen = set(project.get("packages", [])) | {SDK_FRAMEWORKS[n] for n in project.get("sdks", []) if n in SDK_FRAMEWORKS}
    return [n for n in UNSUPPORTED_FRAMEWORKS if n in seen]


def frameworks_named(result: dict) -> list:
    return sorted({n for p in result["projects"] for n in project_frameworks(p)})


def is_generated(path: str, read) -> bool:
    base = path.rsplit("/", 1)[-1].lower()
    if base.endswith((".designer.cs", ".g.cs", ".g.i.cs")):
        return True
    head = (read(path) or "").splitlines()[:10]
    return any("<auto-generated" in line for line in head)
