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
