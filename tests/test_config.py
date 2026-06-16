"""Tests for configuration loading."""

from pathlib import Path

import pytest

from agent_assistant.config import load_config

ENV_VARS = [
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "ORCHESTRATOR_MODEL",
    "PM_MODEL",
    "ARCHITECT_MODEL",
    "CODER_MODEL",
    "REVIEWER_MODEL",
    "TESTER_MODEL",
    "MAX_FEEDBACK_RETRIES",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Remove all agent-assistant env vars before each test."""
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_load_config_defaults():
    """Config loads with sensible defaults when no .env exists."""
    config = load_config(env_path=Path("/nonexistent/.env"))
    assert config.base_url == "https://api.deepseek.com"
    assert config.max_feedback_retries == 3
    assert config.models.orchestrator == "deepseek-chat"


def test_load_config_from_env_vars(monkeypatch):
    """Config reads values from environment variables."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-123")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://custom.api.com")
    monkeypatch.setenv("ORCHESTRATOR_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("CODER_MODEL", "deepseek-coder")
    monkeypatch.setenv("MAX_FEEDBACK_RETRIES", "5")

    config = load_config(env_path=Path("/nonexistent/.env"))
    assert config.api_key == "test-key-123"
    assert config.base_url == "https://custom.api.com"
    assert config.models.orchestrator == "deepseek-v4-pro"
    assert config.models.coder == "deepseek-coder"
    assert config.max_feedback_retries == 5


def test_load_config_from_dotenv(tmp_path):
    """Config reads values from a .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=from-dotenv\nPM_MODEL=deepseek-v4-pro\n")

    config = load_config(env_path=env_file)
    assert config.api_key == "from-dotenv"
    assert config.models.pm == "deepseek-v4-pro"


def test_per_agent_model_defaults():
    """All agent models default to deepseek-chat."""
    config = load_config(env_path=Path("/nonexistent/.env"))
    assert config.models.pm == "deepseek-chat"
    assert config.models.architect == "deepseek-chat"
    assert config.models.coder == "deepseek-chat"
    assert config.models.reviewer == "deepseek-chat"
    assert config.models.tester == "deepseek-chat"
