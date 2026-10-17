"""The shared sandbox and file operations. No shell commands are exposed."""

import os
import re
import stat
from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError

from config import EXTENSIONS, MAX_BYTES


class Files:
    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.root = root.resolve()

    def path(self, value: str, *, directory=False) -> Path:
        """Reject Windows aliases and links before checking resolved ancestry."""
        value = value.replace("\\", "/")
        parts = value.split("/")
        if value.startswith("/") or ":" in value or "\x00" in value:
            raise ToolError("Use a relative path inside workspace; absolute paths and streams are forbidden.")
        for part in parts:
            if part == ".." or (part.startswith(".") and part != "."):
                raise ToolError("Traversal and hidden paths are forbidden.")
            if part not in {"", "."} and (
                part.endswith((" ", ".")) or re.search(r'[<>"|?*\x00-\x1f]', part)
                or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\..*)?", part)
            ):
                raise ToolError("Invalid or reserved Windows filename.")
        candidate = self.root
        for part in parts:
            if part in {"", "."}:
                continue
            candidate /= part
            if candidate.is_symlink() or candidate.is_junction():
                raise ToolError("Symbolic links and junctions are forbidden.")
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.root):
            raise ToolError("Path escapes workspace.")
        if not directory and (resolved == self.root or resolved.suffix.lower() not in EXTENSIONS):
            raise ToolError("Only .md, .txt, .json and .csv files are allowed.")
        if resolved.is_file() and resolved.stat().st_nlink > 1:
            raise ToolError("Hard-linked files are forbidden.")
        return resolved

    def text(self, path: Path) -> str:
        if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
            raise ToolError("Text file does not exist.")
        if path.stat().st_size > MAX_BYTES:
            raise ToolError("File exceeds the 256 KiB limit.")
        try:
            data = path.read_bytes()
            if len(data) > MAX_BYTES or b"\x00" in data:
                raise ToolError("File is too large or contains binary data.")
            return data.decode("utf-8")
        except UnicodeDecodeError:
            raise ToolError("File must contain UTF-8 text.") from None

    def list_files(self, path=".", limit=100):
        folder = self.path(path, directory=True)
        if not folder.is_dir():
            raise ToolError("Directory does not exist.")
        entries = []
        truncated = False
        with os.scandir(folder) as children:
            for i, entry in enumerate(children):
                if i >= 1000:
                    truncated = True
                    break
                try:
                    item = self.path(str(Path(entry.path).relative_to(self.root)), directory=entry.is_dir())
                except ToolError:
                    continue
                if len(entries) >= limit:
                    truncated = True
                    break
                entries.append({"path": item.relative_to(self.root).as_posix(),
                                "type": "directory" if item.is_dir() else "file"})
        return {"entries": entries, "truncated": truncated}
