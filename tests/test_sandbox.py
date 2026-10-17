from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from tools import Files


@pytest.fixture
def files(tmp_path):
    return Files(tmp_path / "workspace")


@pytest.mark.parametrize("path", ["../outside.txt", "..\\outside.txt", "C:/outside.txt", "C:outside.txt",
    "\\\\host\\share\\x.txt", ".env", ".git/config", "x.txt:secret", "CON.txt", "x. /test.txt"])
def test_escape_or_alias_rejected(files, path):
    with pytest.raises(ToolError):
        files.path(path)


def test_list_limits_and_hidden_files(files):
    for name in ["one.md", "two.txt", ".env", "image.png"]:
        (files.root / name).write_text("sample")
    result = files.list_files(limit=1)
    assert len(result["entries"]) == 1
    assert result["truncated"]


def test_junction_escape(files, tmp_path):
    import subprocess
    outside = tmp_path / "outside"
    outside.mkdir()
    link = files.root / "linked"
    # mklink /J does not need administrator privileges on Windows.
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
    if result.returncode:
        pytest.skip("Junction creation is unavailable")
    with pytest.raises(ToolError):
        files.path("linked/new.txt")
    assert files.list_files()["entries"] == []
