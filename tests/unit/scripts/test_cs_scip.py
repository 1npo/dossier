import base64
import hashlib
import io
import zipfile

import pytest

import cs_scip
import shared_tools
import toolcheck


def make_nupkg(members=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in (members or {"tools/net10.0/any/scip-dotnet.dll": b"dll", "tools/net8.0/any/scip-dotnet.dll": b"dll8"}).items():
            z.writestr(name, data)
    return buf.getvalue()


def tool_for(data):
    sha = base64.b64encode(hashlib.sha512(data).digest()).decode()
    return {"id": "scip-dotnet", "version": "0.2.16", "nupkg": {"url": "https://example.invalid/x.nupkg", "sha512": sha}}


class Fetch:
    def __init__(self, data):
        self.data = data
        self.calls = 0

    def __call__(self, url, dest, timeout):
        self.calls += 1
        dest.write_bytes(self.data)


class TestInstallDir:
    def test_path_sits_under_the_tools_cache_with_the_version(self, tmp_path):
        folder = cs_scip.install_dir(tmp_path, "0.2.16")

        assert folder == tmp_path / ".dossier-tools" / "dotnet" / "scip-dotnet-0.2.16"


class TestEnsureInstalled:
    def test_right_bytes_install_and_write_the_marker(self, tmp_path):
        data = make_nupkg()

        folder = cs_scip.ensure_installed(tmp_path, tool_for(data), 30, fetch=Fetch(data))

        assert (folder / "tools/net10.0/any/scip-dotnet.dll").read_bytes() == b"dll"
        assert (folder / ".installed").read_text().strip() == tool_for(data)["nupkg"]["sha512"]

    def test_second_call_does_not_fetch_again(self, tmp_path):
        data = make_nupkg()
        fetch = Fetch(data)
        cs_scip.ensure_installed(tmp_path, tool_for(data), 30, fetch=fetch)

        cs_scip.ensure_installed(tmp_path, tool_for(data), 30, fetch=fetch)

        assert fetch.calls == 1

    def test_wrong_bytes_raise_the_checksum_error_and_leave_nothing(self, tmp_path):
        tool = tool_for(make_nupkg())

        with pytest.raises(shared_tools.ToolError, match="did not match its pinned checksum"):
            cs_scip.ensure_installed(tmp_path, tool, 30, fetch=Fetch(b"not the package"))

        assert not cs_scip.install_dir(tmp_path, "0.2.16").exists()

    def test_member_with_dotdot_is_refused(self, tmp_path):
        data = make_nupkg({"../x": b"evil"})

        with pytest.raises(shared_tools.ToolError):
            cs_scip.ensure_installed(tmp_path, tool_for(data), 30, fetch=Fetch(data))

        assert not (tmp_path / ".dossier-tools" / "dotnet" / "x").exists()

    def test_absolute_member_is_refused(self, tmp_path):
        data = make_nupkg({"/etc/x": b"evil"})

        with pytest.raises(shared_tools.ToolError):
            cs_scip.ensure_installed(tmp_path, tool_for(data), 30, fetch=Fetch(data))


class TestToolDll:
    def build(self, tmp_path):
        data = make_nupkg()
        return cs_scip.ensure_installed(tmp_path, tool_for(data), 30, fetch=Fetch(data))

    def test_highest_installed_runtime_wins(self, tmp_path):
        folder = self.build(tmp_path)

        assert cs_scip.tool_dll(folder, [8, 10]) == folder / "tools/net10.0/any/scip-dotnet.dll"

    def test_only_eight_gives_net8(self, tmp_path):
        folder = self.build(tmp_path)

        assert cs_scip.tool_dll(folder, [8]) == folder / "tools/net8.0/any/scip-dotnet.dll"

    def test_unsupported_runtime_gives_none(self, tmp_path):
        folder = self.build(tmp_path)

        assert cs_scip.tool_dll(folder, [7]) is None


class TestPinnedEntry:
    def entry(self):
        return {t["id"]: t for t in toolcheck.load_tools()["tools"]}["scip-dotnet"]

    def test_pin_is_the_gated_release(self):
        e = self.entry()

        assert (e["version"], e["published"]) == ("0.2.16", "2026-10-21")
        assert e["nupkg"]["sha512"].startswith("UUaPQCnqIWFYGXaKtgjieBP0WR0uH8L55pwqhtOJH")

    def test_cards_are_filled(self):
        assert self.entry()["cards"] == ["components.catalog", "interactions.flows", "interactions.graph"]

    def test_package_list_is_marked_not_run(self):
        e = {t["id"]: t for t in toolcheck.load_tools()["tools"]}["dotnet-package-list"]

        assert e["open"].startswith("Not run:")


class TestDoctorText:
    def test_hash_checked_package_is_named(self):
        report = toolcheck.preflight(["C#"], path="/nonexistent")
        text = toolcheck.format_text(report)

        assert "scip-dotnet 0.2.16 from a hash-checked NuGet package" in text
