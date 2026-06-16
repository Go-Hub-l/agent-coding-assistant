"""Tests for project context scanner and summarizer."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent_assistant.llm.client import ChatResponse, LLMClient
from agent_assistant.project_context.scanner import FileInfo, ProjectScanner, ScanResult
from agent_assistant.project_context.summarizer import ProjectSummarizer


# --- Scanner tests ---


@pytest.fixture
def sample_project(tmp_path):
    """Create a minimal Python project for testing."""
    (tmp_path / "main.py").write_text(
        'from flask import Flask\n\napp = Flask(__name__)\n\ndef create_app():\n    return app\n'
    )
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "__init__.py").write_text("")
    (tmp_path / "models" / "user.py").write_text(
        "class User:\n    pass\n\nclass UserProfile:\n    pass\n\ndef get_user():\n    pass\n"
    )
    (tmp_path / "requirements.txt").write_text("flask>=2.0\nsqlalchemy\n")
    return tmp_path


def test_scanner_finds_files(sample_project):
    """Scanner discovers files in the project tree."""
    scanner = ProjectScanner(sample_project)
    result = scanner.scan()
    assert len(result.file_tree) > 0
    assert any("main.py" in f for f in result.file_tree)


def test_scanner_extracts_dependencies(sample_project):
    """Scanner parses requirements.txt for dependencies."""
    scanner = ProjectScanner(sample_project)
    result = scanner.scan()
    assert "python" in result.dependencies
    assert "flask" in result.dependencies["python"]
    assert "sqlalchemy" in result.dependencies["python"]


def test_scanner_extracts_python_symbols(sample_project):
    """Scanner extracts class and function names from Python files."""
    scanner = ProjectScanner(sample_project)
    result = scanner.scan()
    user_file = next((f for f in result.files if "user.py" in f.path), None)
    assert user_file is not None
    assert "User" in user_file.classes
    assert "UserProfile" in user_file.classes
    assert "get_user" in user_file.functions


def test_scanner_finds_entry_points(sample_project):
    """Scanner identifies main.py as an entry point."""
    scanner = ProjectScanner(sample_project)
    result = scanner.scan()
    assert any("main.py" in ep for ep in result.entry_points)


def test_scanner_skips_hidden_dirs(tmp_path):
    """Scanner skips __pycache__ and .git directories."""
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cached.pyc").write_text("")
    (tmp_path / ".git").mkdir()
    (tmp_path / "real.py").write_text("x = 1")

    scanner = ProjectScanner(tmp_path)
    result = scanner.scan()
    assert not any("__pycache__" in f for f in result.file_tree)
    assert not any(".git" in f for f in result.file_tree)


def test_scanner_respects_max_depth(tmp_path):
    """Scanner stops at max_depth."""
    deep = tmp_path / "a" / "b" / "c" / "d" / "e"
    deep.mkdir(parents=True)
    (deep / "deep.py").write_text("x = 1")
    (tmp_path / "top.py").write_text("x = 1")

    scanner = ProjectScanner(tmp_path, max_depth=2)
    result = scanner.scan()
    assert not any("deep.py" in f for f in result.file_tree)


def test_scanner_handles_syntax_error(tmp_path):
    """Scanner handles Python files with syntax errors gracefully."""
    (tmp_path / "broken.py").write_text("def foo(\n  invalid syntax\n")
    scanner = ProjectScanner(tmp_path)
    result = scanner.scan()
    # Should not crash
    assert len(result.files) >= 1


def test_scan_result_to_dict(sample_project):
    """ScanResult serializes to a dict."""
    scanner = ProjectScanner(sample_project)
    result = scanner.scan()
    d = result.to_dict()
    assert "file_tree" in d
    assert "dependencies" in d
    assert "files" in d
    assert "entry_points" in d


# --- Summarizer tests ---


SAMPLE_SUMMARY_RESPONSE = json.dumps({
    "project_type": "Web application",
    "tech_stack": ["Flask", "SQLAlchemy"],
    "architecture": "MVC with Flask routes and SQLAlchemy models",
    "key_modules": [
        {"name": "models", "purpose": "Data models for users"},
    ],
    "patterns": ["MVC"],
})


def test_summarizer_produces_summary(sample_project):
    """ProjectSummarizer generates a semantic summary from scan data."""
    scanner = ProjectScanner(sample_project)
    scan_result = scanner.scan()

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.chat.return_value = ChatResponse(
        content=SAMPLE_SUMMARY_RESPONSE, model="deepseek-chat", usage={}
    )

    summarizer = ProjectSummarizer(mock_llm)
    result = summarizer.summarize(scan_result)

    assert "summary" in result
    assert "scan_data" in result
    assert result["summary"]["project_type"] == "Web application"
    assert "Flask" in result["summary"]["tech_stack"]


def test_summarizer_handles_markdown_fences():
    """Summarizer handles LLM responses wrapped in markdown fences."""
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.chat.return_value = ChatResponse(
        content=f"```json\n{SAMPLE_SUMMARY_RESPONSE}\n```",
        model="deepseek-chat",
        usage={},
    )
    scan = ScanResult(
        root_dir="/test", file_tree=["main.py"], dependencies={},
        files=[], entry_points=[],
    )
    summarizer = ProjectSummarizer(mock_llm)
    result = summarizer.summarize(scan)
    assert result["summary"]["project_type"] == "Web application"


def test_summarizer_invalid_json_raises():
    """Summarizer raises on invalid JSON from LLM."""
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.chat.return_value = ChatResponse(
        content="Not JSON", model="deepseek-chat", usage={}
    )
    scan = ScanResult(
        root_dir="/test", file_tree=[], dependencies={},
        files=[], entry_points=[],
    )
    summarizer = ProjectSummarizer(mock_llm)
    with pytest.raises(json.JSONDecodeError):
        summarizer.summarize(scan)
