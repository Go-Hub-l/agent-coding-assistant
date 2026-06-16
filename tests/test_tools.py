"""Tests for tool access layer."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent_assistant.pipeline.agent import AgentRole
from agent_assistant.tools.base import PermissionError, ToolError, ToolRegistry
from agent_assistant.tools.file_tools import ListDirectoryTool, ReadFileTool, WriteFileTool
from agent_assistant.tools.permissions import TOOL_PERMISSIONS, get_tools_for_role


# --- ReadFileTool tests ---


def test_read_file_success(tmp_path):
    """read_file returns file contents."""
    (tmp_path / "hello.py").write_text("print('hello')")
    tool = ReadFileTool(tmp_path)
    assert tool.execute(path="hello.py") == "print('hello')"


def test_read_file_not_found(tmp_path):
    """read_file raises ToolError for missing files."""
    tool = ReadFileTool(tmp_path)
    with pytest.raises(ToolError, match="File not found"):
        tool.execute(path="missing.py")


def test_read_file_not_a_file(tmp_path):
    """read_file raises ToolError for directories."""
    (tmp_path / "subdir").mkdir()
    tool = ReadFileTool(tmp_path)
    with pytest.raises(ToolError, match="Not a file"):
        tool.execute(path="subdir")


# --- WriteFileTool tests ---


def test_write_file_success(tmp_path):
    """write_file creates files with content."""
    tool = WriteFileTool(tmp_path)
    result = tool.execute(path="output.txt", content="hello world")
    assert "11" in result  # byte count
    assert (tmp_path / "output.txt").read_text() == "hello world"


def test_write_file_creates_parent_dirs(tmp_path):
    """write_file creates parent directories if needed."""
    tool = WriteFileTool(tmp_path)
    tool.execute(path="deep/nested/file.txt", content="nested")
    assert (tmp_path / "deep" / "nested" / "file.txt").read_text() == "nested"


# --- ListDirectoryTool tests ---


def test_list_directory_success(tmp_path):
    """list_directory returns files and directories."""
    (tmp_path / "file.py").write_text("")
    (tmp_path / "subdir").mkdir()
    tool = ListDirectoryTool(tmp_path)
    entries = tool.execute()
    names = {e["name"] for e in entries}
    assert "file.py" in names
    assert "subdir" in names


def test_list_directory_types(tmp_path):
    """list_directory correctly identifies file vs directory types."""
    (tmp_path / "file.py").write_text("")
    (tmp_path / "subdir").mkdir()
    tool = ListDirectoryTool(tmp_path)
    entries = {e["name"]: e["type"] for e in tool.execute()}
    assert entries["file.py"] == "file"
    assert entries["subdir"] == "directory"


def test_list_directory_not_found(tmp_path):
    """list_directory raises ToolError for missing directories."""
    tool = ListDirectoryTool(tmp_path)
    with pytest.raises(ToolError, match="Directory not found"):
        tool.execute(path="nonexistent")


# --- ToolRegistry tests ---


def test_registry_permits_allowed_tool(tmp_path):
    """ToolRegistry allows invocation of permitted tools."""
    (tmp_path / "test.py").write_text("code")
    registry = ToolRegistry(allowed_tools={"read_file"}, working_dir=tmp_path)
    result = registry.invoke("read_file", path="test.py")
    assert result == "code"


def test_registry_blocks_unauthorized_tool(tmp_path):
    """ToolRegistry raises PermissionError for unauthorized tools."""
    registry = ToolRegistry(allowed_tools={"read_file"}, working_dir=tmp_path)
    with pytest.raises(PermissionError, match="not permitted"):
        registry.invoke("write_file", path="test.py", content="x")


def test_registry_available_tools(tmp_path):
    """ToolRegistry lists all registered tools."""
    registry = ToolRegistry(allowed_tools=set(), working_dir=tmp_path)
    assert "read_file" in registry.available_tools
    assert "write_file" in registry.available_tools
    assert "list_directory" in registry.available_tools


def test_registry_permitted_tools(tmp_path):
    """ToolRegistry.pmitted_tools shows intersection of allowed and registered."""
    registry = ToolRegistry(
        allowed_tools={"read_file", "nonexistent_tool"},
        working_dir=tmp_path,
    )
    assert registry.permitted_tools == {"read_file"}


def test_registry_unknown_tool_raises(tmp_path):
    """ToolRegistry raises ToolError when invoking a non-registered tool."""
    registry = ToolRegistry(allowed_tools={"magic_tool"}, working_dir=tmp_path)
    with pytest.raises(ToolError, match="Unknown tool"):
        registry.invoke("magic_tool")


# --- Permission map tests ---


def test_pm_has_read_only_tools():
    """PM role has read-only tool access."""
    tools = get_tools_for_role(AgentRole.PM)
    assert "read_file" in tools
    assert "list_directory" in tools
    assert "write_file" not in tools


def test_coder_has_write_access():
    """Coder role has write_file permission."""
    tools = get_tools_for_role(AgentRole.CODER)
    assert "write_file" in tools
    assert "read_file" in tools


def test_reviewer_has_read_only():
    """Reviewer role has read-only access (no write)."""
    tools = get_tools_for_role(AgentRole.REVIEWER)
    assert "read_file" in tools
    assert "write_file" not in tools


def test_all_roles_have_permissions():
    """Every AgentRole has a permission entry."""
    for role in AgentRole:
        tools = get_tools_for_role(role)
        assert len(tools) > 0, f"Role {role.value} has no tools"
