"""Tests for intent specification module."""

import json
from unittest.mock import MagicMock

import pytest

from agent_assistant.llm.client import ChatMessage, ChatResponse, LLMClient
from agent_assistant.orchestrator.intent import (
    IntentDocument,
    _extract_json,
    correct_intent,
    parse_intent,
)


# --- IntentDocument tests ---


def test_intent_document_creation():
    """IntentDocument can be created with all fields."""
    intent = IntentDocument(
        feature="User login with JWT",
        constraints=["Must use bcrypt"],
        target_modules=["auth", "api"],
        assumptions=["Existing user model"],
    )
    assert intent.feature == "User login with JWT"
    assert len(intent.constraints) == 1
    assert len(intent.target_modules) == 2


def test_intent_document_defaults():
    """IntentDocument has empty defaults for list fields."""
    intent = IntentDocument(feature="A feature")
    assert intent.constraints == []
    assert intent.target_modules == []
    assert intent.assumptions == []


def test_intent_document_to_json():
    """IntentDocument serializes to valid JSON."""
    intent = IntentDocument(feature="Test", constraints=["c1"], target_modules=["m1"])
    data = json.loads(intent.to_json())
    assert data["feature"] == "Test"
    assert data["constraints"] == ["c1"]


def test_intent_document_from_json():
    """IntentDocument can be parsed from JSON."""
    raw = '{"feature": "Login", "constraints": ["JWT"], "target_modules": ["auth"], "assumptions": []}'
    intent = IntentDocument.from_json(raw)
    assert intent.feature == "Login"
    assert intent.constraints == ["JWT"]


def test_intent_document_from_json_missing_optional():
    """IntentDocument.from_json handles missing optional fields."""
    raw = '{"feature": "Login"}'
    intent = IntentDocument.from_json(raw)
    assert intent.feature == "Login"
    assert intent.constraints == []
    assert intent.target_modules == []


def test_intent_document_format_for_display():
    """format_for_display produces readable output."""
    intent = IntentDocument(
        feature="User login",
        constraints=["Use JWT"],
        target_modules=["auth"],
        assumptions=["Existing DB"],
    )
    display = intent.format_for_display()
    assert "User login" in display
    assert "Use JWT" in display
    assert "auth" in display
    assert "Existing DB" in display


# --- _extract_json tests ---


def test_extract_json_plain():
    """Extract JSON from plain text without fences."""
    text = '{"feature": "test"}'
    assert _extract_json(text) == '{"feature": "test"}'


def test_extract_json_with_markdown_fences():
    """Extract JSON from markdown code block."""
    text = '```json\n{"feature": "test"}\n```'
    assert _extract_json(text) == '{"feature": "test"}'


# --- parse_intent tests ---


def test_parse_intent_success():
    """parse_intent returns an IntentDocument from LLM response."""
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.chat.return_value = ChatResponse(
        content='{"feature": "User login", "constraints": ["JWT"], "target_modules": ["auth"], "assumptions": ["DB exists"]}',
        model="deepseek-v4-pro",
        usage={},
    )

    intent = parse_intent(mock_llm, "add user login")

    assert intent.feature == "User login"
    assert intent.constraints == ["JWT"]
    mock_llm.chat.assert_called_once()
    # Verify system prompt was sent
    messages = mock_llm.chat.call_args[0][0]
    assert messages[0].role == "system"
    assert messages[1].role == "user"
    assert messages[1].content == "add user login"


def test_parse_intent_with_markdown_fences():
    """parse_intent handles LLM responses wrapped in markdown fences."""
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.chat.return_value = ChatResponse(
        content='```json\n{"feature": "Test", "constraints": [], "target_modules": [], "assumptions": []}\n```',
        model="deepseek-v4-pro",
        usage={},
    )

    intent = parse_intent(mock_llm, "test")
    assert intent.feature == "Test"


def test_parse_intent_invalid_json_raises():
    """parse_intent raises on invalid JSON from LLM."""
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.chat.return_value = ChatResponse(
        content="This is not JSON at all",
        model="deepseek-v4-pro",
        usage={},
    )

    with pytest.raises(json.JSONDecodeError):
        parse_intent(mock_llm, "test")


# --- correct_intent tests ---


def test_correct_intent_success():
    """correct_intent applies corrections and returns updated document."""
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.chat.return_value = ChatResponse(
        content='{"feature": "User login with OAuth", "constraints": ["JWT", "OAuth2"], "target_modules": ["auth"], "assumptions": []}',
        model="deepseek-v4-pro",
        usage={},
    )

    original = IntentDocument(feature="User login", constraints=["JWT"])
    updated = correct_intent(mock_llm, original, "Also support OAuth2")

    assert updated.feature == "User login with OAuth"
    assert "OAuth2" in updated.constraints
