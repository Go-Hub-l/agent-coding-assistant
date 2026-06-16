"""Tests for LLM client."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from agent_assistant.config import Config
from agent_assistant.llm.client import ChatMessage, ChatResponse, LLMClient


@pytest.fixture
def config():
    return Config(api_key="test-key", base_url="https://api.deepseek.com")


def test_llm_client_init(config):
    """LLMClient initializes with config defaults."""
    client = LLMClient(config)
    assert client._base_url == "https://api.deepseek.com"
    assert client._api_key == "test-key"
    assert client._model == "deepseek-chat"


def test_llm_client_custom_model(config):
    """LLMClient accepts a custom model override."""
    client = LLMClient(config, model="deepseek-v4-pro")
    assert client._model == "deepseek-v4-pro"


def test_llm_client_chat_success(config):
    """LLMClient.chat returns a ChatResponse from a successful API call."""
    client = LLMClient(config)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello!"}}],
        "model": "deepseek-chat",
        "usage": {"total_tokens": 10},
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as MockClient:
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.post.return_value = mock_response
        MockClient.return_value = mock_ctx

        messages = [
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="Hi"),
        ]
        result = client.chat(messages)

    assert isinstance(result, ChatResponse)
    assert result.content == "Hello!"
    assert result.model == "deepseek-chat"
    assert result.usage == {"total_tokens": 10}


def test_llm_client_strips_trailing_slash():
    """LLMClient strips trailing slash from base URL."""
    config = Config(api_key="key", base_url="https://api.deepseek.com/")
    client = LLMClient(config)
    assert client._base_url == "https://api.deepseek.com"


def test_chat_message_dataclass():
    """ChatMessage stores role and content."""
    msg = ChatMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"
