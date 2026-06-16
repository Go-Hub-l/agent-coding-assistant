"""File system tools — read, write, and list operations on the codebase."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_assistant.tools.base import Tool, ToolError


class ReadFileTool(Tool):
    """Read the contents of a file."""

    def __init__(self, working_dir: Path):
        self._working_dir = working_dir

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents of a file relative to the project directory."

    def execute(self, path: str, **kwargs: Any) -> str:
        """Read a file and return its contents as a string."""
        file_path = self._resolve_path(path)
        if not file_path.exists():
            raise ToolError(f"File not found: {path}")
        if not file_path.is_file():
            raise ToolError(f"Not a file: {path}")
        return file_path.read_text(encoding="utf-8")

    def _resolve_path(self, path: str) -> Path:
        return (self._working_dir / path).resolve()


class WriteFileTool(Tool):
    """Write content to a file, creating directories as needed."""

    def __init__(self, working_dir: Path):
        self._working_dir = working_dir

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file. Creates parent directories if needed."

    def execute(self, path: str, content: str, **kwargs: Any) -> str:
        """Write content to a file. Returns confirmation message."""
        file_path = self._resolve_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Written {len(content)} bytes to {path}"

    def _resolve_path(self, path: str) -> Path:
        return (self._working_dir / path).resolve()


class ListDirectoryTool(Tool):
    """List files and directories in a given path."""

    def __init__(self, working_dir: Path):
        self._working_dir = working_dir

    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def description(self) -> str:
        return "List files and subdirectories at a given path."

    def execute(self, path: str = ".", **kwargs: Any) -> list[dict[str, str]]:
        """List directory contents. Returns list of {name, type} dicts."""
        dir_path = self._resolve_path(path)
        if not dir_path.exists():
            raise ToolError(f"Directory not found: {path}")
        if not dir_path.is_dir():
            raise ToolError(f"Not a directory: {path}")

        entries = []
        for item in sorted(dir_path.iterdir()):
            entries.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
            })
        return entries

    def _resolve_path(self, path: str) -> Path:
        return (self._working_dir / path).resolve()
