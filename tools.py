"""The shared sandbox and file operations. No shell commands are exposed."""

import os
import re
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError

from config import EXTENSIONS, HANDOFF, MAX_BYTES


class Files:
    def __init__(self, root: Path):
        if root.is_symlink() or root.is_junction():
            raise ToolError("Workspace root must be an ordinary directory, not a link.")
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

    def read_file(self, path, start_line=1, max_lines=100):
        lines = self.text(self.path(path)).splitlines()
        selected = lines[start_line - 1:start_line - 1 + max_lines]
        # A single enormous line must not defeat chunking.
        output = "\n".join(f"{i}: {line}" for i, line in enumerate(selected, start_line))
        if len(output.encode("utf-8")) > 16000:
            raise ToolError("Selected lines exceed 16 KiB; use fewer lines or search_files.")
        end = start_line - 1 + len(selected)
        return {"path": path, "text": output, "total_lines": len(lines),
                "next_line": end + 1 if end < len(lines) else None}

    def save(self, path: Path, content: str):
        data = content.encode("utf-8")
        if len(data) > MAX_BYTES or "\x00" in content:
            raise ToolError("Content must be UTF-8 text without NUL, at most 256 KiB.")
        path.parent.mkdir(parents=True, exist_ok=True)
        # Replace a complete file instead of leaving a partially written file.
        temp = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".write-", delete=False) as stream:
                temp = Path(stream.name)
                stream.write(data)
            os.replace(temp, path)
        finally:
            if temp and temp.exists():
                temp.unlink()
        return {"path": path.relative_to(self.root).as_posix(), "bytes": len(data)}

    def write_file(self, path, content, overwrite=False):
        target = self.path(path)
        if target.exists():
            self.text(target)
            if not overwrite:
                raise ToolError("File already exists. Read it first; explicit overwrite=true is required.")
        return self.save(target, content)

    def str_replace(self, path, old_str, new_str):
        target = self.path(path)
        text = self.text(target)
        if not old_str or text.count(old_str) != 1:
            raise ToolError("old_str must be nonempty and match exactly once; read more context.")
        return self.save(target, text.replace(old_str, new_str, 1))

    def delete_file(self, path, confirm=False):
        target = self.path(path)
        if target.name.lower() in HANDOFF:
            raise ToolError("Handoff records cannot be deleted.")
        self.text(target)
        if not confirm:
            raise ToolError("Deletion requires confirm=true and human approval in your client.")
        target.unlink()
        return {"path": path, "deleted": True}

    def append_file(self, path, content):
        target = self.path(path)
        return self.save(target, self.text(target) + content)

    def file_info(self, path):
        target = self.path(path)
        self.text(target)
        info = target.stat()
        return {"path": path, "bytes": info.st_size,
                "modified_utc": datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat()}

    def search_files(self, query, path=".", max_results=50):
        folder = self.path(path, directory=True)
        if not folder.is_dir():
            raise ToolError("Search path must be a workspace directory.")
        matches, scanned, visited = [], 0, 0
        for current, dirs, names in os.walk(folder, followlinks=False):
            visited += 1
            if visited > 1000:
                return {"matches": matches, "scanned": scanned, "truncated": True}
            safe_dirs = []
            for name in dirs:
                try:
                    self.path(str((Path(current) / name).relative_to(self.root)), directory=True)
                    safe_dirs.append(name)
                except ToolError:
                    pass
            dirs[:] = safe_dirs
            for name in names:
                visited += 1
                if visited > 1000 or scanned >= 200:
                    return {"matches": matches, "scanned": scanned, "truncated": True}
                relative = (Path(current) / name).relative_to(self.root).as_posix()
                try:
                    candidate = self.path(relative)
                    text = self.text(candidate)
                except (ToolError, OSError):
                    continue
                scanned += 1
                for number, line in enumerate(text.splitlines(), 1):
                    if query in line:
                        if len(matches) >= max_results:
                            return {"matches": matches, "scanned": scanned, "truncated": True}
                        pos = line.index(query)
                        snippet = line[max(0, pos - 80):pos + len(query) + 80]
                        matches.append({"path": relative, "line": number, "text": snippet})
        return {"matches": matches, "scanned": scanned, "truncated": False}
