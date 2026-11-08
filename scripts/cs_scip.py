"""scip-dotnet for the C# adapter: install it from a hash-checked NuGet package (plan 011, D3).

No `dotnet tool install` and no NuGet feed at run time. The one network call made in-process is the package download,
which checks a pinned SHA-512 before anything is unpacked. Nothing from the package is run here.
"""
import base64
import hashlib
import urllib.request
import zipfile
from pathlib import Path

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
