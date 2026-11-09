import os
import shutil
import subprocess

import pytest

import cs_scip
import sandbox
import toolcheck

pytestmark = [
    pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1"),
    pytest.mark.skipif(shutil.which("dotnet") is None, reason="needs the .NET runtime (dotnet is not installed)"),
]


class TestRealInstall:
    def test_installed_tool_reports_its_version(self, tmp_path):
        area = tmp_path / "cache" / "repo"
        area.mkdir(parents=True)
        tool = next(t for t in toolcheck.load_tools()["tools"] if t["id"] == "scip-dotnet")
        majors = [int(line.split()[1].split(".")[0]) for line in
                  subprocess.run(["dotnet", "--list-runtimes"], capture_output=True, text=True).stdout.splitlines()
                  if line.startswith("Microsoft.NETCore.App")]

        folder = cs_scip.ensure_installed(area.parent, tool, 900)
        dll = cs_scip.tool_dll(folder, majors)
        result = sandbox.run(["dotnet", str(dll), "--version"], area=area, cwd=tmp_path, stage="test", timeout=120)

        assert result.returncode == 0
        assert result.stdout.read_text().startswith(tool["version"])
