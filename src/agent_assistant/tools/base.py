"""Tool base class and registry — agents interact with the codebase through tools."""

from __future__ import annotations

import abc
from pathlib import Path
from typing import Any


class ToolError(Exception):
    """Raised when a tool execution fails."""


class PermissionError(ToolError):
    """Raised when an agent tries to use an unauthorized tool."""


class Tool(abc.ABC):
    """Abstract base class for all tools available to agents."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique identifier for this tool."""
        ...

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does."""
        ...

    @abc.abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with the given arguments."""
        ...


class ToolRegistry:
    """Registry that manages tool instances and enforces per-role permissions."""

    def __init__(self, allowed_tools: set[str], working_dir: Path):
        """
        Args:
            allowed_tools: Set of tool names this registry permits.
            working_dir: Base directory for file operations.
        """
        self._allowed = allowed_tools
        self._working_dir = working_dir
        self._tools: dict[str, Tool] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        """Register all built-in tools."""
        from agent_assistant.tools.file_tools import (
            ListDirectoryTool,
            ReadFileTool,
            WriteFileTool,
        )

        for tool_cls in (ReadFileTool, WriteFileTool, ListDirectoryTool):
            tool = tool_cls(self._working_dir)
            self._tools[tool.name] = tool

    def invoke(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a tool by name, checking permissions first.

        Raises:
            PermissionError: If the tool is not in the allowed set.
            ToolError: If the tool execution fails.
        """
        if tool_name not in self._allowed:
            raise PermissionError(
                f"Tool '{tool_name}' is not permitted for this agent role. "
                f"Allowed tools: {sorted(self._allowed)}"
            )

        tool = self._tools.get(tool_name)
        if tool is None:
            raise ToolError(f"Unknown tool: '{tool_name}'")

        return tool.execute(**kwargs)

    @property
    def available_tools(self) -> list[str]:
        """List all tools this registry has registered."""
        return list(self._tools.keys())

    @property
    def permitted_tools(self) -> set[str]:
        """List tools the current role is allowed to use."""
        return self._allowed & set(self._tools.keys())
