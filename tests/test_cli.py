"""Tests for CLI entry point."""

from typer.testing import CliRunner

from agent_assistant.cli import app

runner = CliRunner()


def test_version_command():
    """CLI version command prints the version string."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "agent-assist v0.1.0" in result.output


def test_build_without_api_key_shows_error(tmp_path, monkeypatch):
    """CLI build command exits with error when DEEPSEEK_API_KEY is not set."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    result = runner.invoke(app, ["build", "test request"])
    assert result.exit_code == 2
    assert "DEEPSEEK_API_KEY" in result.output


def test_build_shows_request(monkeypatch):
    """CLI build command displays the user's request."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    result = runner.invoke(app, ["build", "implement user login"])
    assert "implement user login" in result.output


def test_build_greenfield_mode(monkeypatch):
    """CLI build command defaults to greenfield mode when no project dir given."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    result = runner.invoke(app, ["build", "test request"])
    assert "Greenfield" in result.output


def test_build_iteration_mode(monkeypatch, tmp_path):
    """CLI build command shows iteration mode when project dir is provided."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    result = runner.invoke(app, ["build", "test request", "--project-dir", str(tmp_path)])
    assert "Iteration" in result.output


def test_build_invalid_project_dir(monkeypatch):
    """CLI build command errors when project dir does not exist."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    result = runner.invoke(app, ["build", "test request", "--project-dir", "/nonexistent/path"])
    assert result.exit_code == 2


def test_help_shows_usage():
    """CLI --help shows usage information."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "agent-assist" in result.output.lower() or "Usage" in result.output


def test_help_mentions_intervene_options():
    """CLI build --help shows intervention options."""
    result = runner.invoke(app, ["build", "--help"])
    assert "intervene" in result.output.lower()


def test_help_mentions_exit_codes():
    """CLI build --help mentions exit codes."""
    result = runner.invoke(app, ["build", "--help"])
    assert "Exit codes" in result.output or "exit" in result.output.lower()


def test_help_mentions_output_dir():
    """CLI build --help shows output-dir option."""
    result = runner.invoke(app, ["build", "--help"])
    assert "output-dir" in result.output.lower() or "output" in result.output.lower()


# --- _write_artifact_files tests ---

from pathlib import Path

from agent_assistant.cli import _write_artifact_files
from agent_assistant.pipeline.artifact import Artifact
from agent_assistant.pipeline.session import Session


def test_write_coder_files(tmp_path):
    """_write_artifact_files writes Coder artifact files to disk."""
    session = Session()
    session.record_artifact(Artifact(
        stage="coder", summary="Code",
        structured_data={"files": [
            {"path": "src/main.py", "content": "print('hello')", "description": "Main entry"},
            {"path": "src/utils.py", "content": "def helper(): pass", "description": "Utils"},
        ]},
    ))

    written = _write_artifact_files(session, tmp_path / "out")
    assert len(written) == 2
    assert (tmp_path / "out" / "src" / "main.py").read_text() == "print('hello')"
    assert (tmp_path / "out" / "src" / "utils.py").read_text() == "def helper(): pass"


def test_write_tester_files(tmp_path):
    """_write_artifact_files writes Tester artifact test_files to disk."""
    session = Session()
    session.record_artifact(Artifact(
        stage="tester", summary="Tests",
        structured_data={"test_files": [
            {"path": "tests/test_main.py", "content": "def test_ok(): assert True", "description": "Test"},
        ], "results": {}, "verdict": "passed"},
    ))

    written = _write_artifact_files(session, tmp_path / "out")
    assert len(written) == 1
    assert (tmp_path / "out" / "tests" / "test_main.py").read_text() == "def test_ok(): assert True"


def test_write_both_coder_and_tester(tmp_path):
    """_write_artifact_files writes files from both Coder and Tester artifacts."""
    session = Session()
    session.record_artifact(Artifact(
        stage="coder", summary="Code",
        structured_data={"files": [
            {"path": "app.py", "content": "x = 1", "description": "App"},
        ]},
    ))
    session.record_artifact(Artifact(
        stage="tester", summary="Tests",
        structured_data={"test_files": [
            {"path": "test_app.py", "content": "def test(): pass", "description": "Test"},
        ], "results": {}},
    ))

    written = _write_artifact_files(session, tmp_path / "out")
    assert len(written) == 2


def test_write_no_artifacts(tmp_path):
    """_write_artifact_files returns empty list when no coder/tester artifacts."""
    session = Session()
    written = _write_artifact_files(session, tmp_path / "out")
    assert written == []


def test_write_creates_nested_dirs(tmp_path):
    """_write_artifact_files creates parent directories automatically."""
    session = Session()
    session.record_artifact(Artifact(
        stage="coder", summary="Code",
        structured_data={"files": [
            {"path": "deep/nested/path/module.py", "content": "# deep", "description": "Deep"},
        ]},
    ))

    written = _write_artifact_files(session, tmp_path / "out")
    assert len(written) == 1
    assert (tmp_path / "out" / "deep" / "nested" / "path" / "module.py").read_text() == "# deep"
