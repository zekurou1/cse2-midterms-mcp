import os

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from config import MAX_BYTES
from tools import Files


@pytest.fixture
def files(tmp_path):
    return Files(tmp_path / "workspace")


def test_file_lifecycle(files):
    files.write_file("notes/a.md", "one\ntwo\nthree")
    result = files.read_file("notes/a.md", 2, 1)
    assert result["text"] == "2: two" and result["next_line"] == 3
    files.str_replace("notes/a.md", "two", "second")
    files.append_file("notes/a.md", "\nfour")
    assert files.search_files("second")["matches"][0]["line"] == 2
    assert files.file_info("notes/a.md")["bytes"] == len("one\nsecond\nthree\nfour")
    with pytest.raises(ToolError, match="confirm"):
        files.delete_file("notes/a.md")
    files.delete_file("notes/a.md", True)
    assert not (files.root / "notes/a.md").exists()


def test_overwrite_and_ambiguous_replacement(files):
    files.write_file("a.txt", "same same")
    with pytest.raises(ToolError, match="exists"):
        files.write_file("a.txt", "lost")
    for old in ["same", "missing", ""]:
        with pytest.raises(ToolError, match="exactly once"):
            files.str_replace("a.txt", old, "new")
    assert (files.root / "a.txt").read_text() == "same same"
    files.write_file("a.txt", "replacement", True)


def test_protect_handoff_and_directories(files):
    files.write_file("CHECKPOINTS.md", "checkpoint")
    with pytest.raises(ToolError, match="Handoff"):
        files.delete_file("CHECKPOINTS.md", True)
    with pytest.raises(ToolError):
        files.delete_file(".", True)


def test_size_and_binary_limits(files):
    for content in ["a" * (MAX_BYTES + 1), "binary\x00data"]:
        with pytest.raises(ToolError):
            files.write_file("a.txt", content)
    files.write_file("a.txt", "a" * MAX_BYTES)
    with pytest.raises(ToolError):
        files.append_file("a.txt", "overflow")
    assert (files.root / "a.txt").stat().st_size == MAX_BYTES
    (files.root / "bad.txt").write_bytes(b"\xff\x00")
    with pytest.raises(ToolError):
        files.read_file("bad.txt")
    with pytest.raises(ToolError, match="16 KiB"):
        files.read_file("a.txt")


def test_search_literal_limits_and_long_line(files):
    files.write_file("a.md", "x.y\nx.y\nxay\n" + "a" * 20000 + "needle")
    assert len(files.search_files("x.y")["matches"]) == 2
    assert files.search_files("x.y", max_results=1)["truncated"]
    match = files.search_files("needle")["matches"][0]
    assert len(match["text"]) < 200


def test_hardlink_rejected(files, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("keep")
    os.link(outside, files.root / "linked.txt")
    with pytest.raises(ToolError, match="Hard-linked"):
        files.write_file("linked.txt", "change", True)
    assert outside.read_text() == "keep"


def test_escaping_new_parent(files):
    with pytest.raises(ToolError):
        files.write_file("../outside/new.txt", "bad")
    assert not (files.root.parent / "outside").exists()
