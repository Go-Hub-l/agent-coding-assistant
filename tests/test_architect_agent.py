"""Tests for Architect Agent."""

import json
from unittest.mock import MagicMock

import pytest

from agent_assistant.config import Config
from agent_assistant.llm.client import ChatResponse, LLMClient
from agent_assistant.orchestrator.intent import IntentDocument
from agent_assistant.pipeline.agent import AgentRole
from agent_assistant.pipeline.artifact import Artifact
from agent_assistant.pipeline.context import AgentContext
from agent_assistant.agents.architect import ArchitectAgent


SAMPLE_RESPONSE = json.dumps({
    "modules": [
        {"name": "auth", "purpose": "User authentication", "responsibilities": ["JWT tokens", "Password hashing"]},
        {"name": "api", "purpose": "REST API endpoints", "responsibilities": ["Login endpoint", "Logout endpoint"]},
    ],
    "interfaces": [
        {"name": "AuthService", "type": "service", "description": "Handles auth logic", "methods": ["login(email, password)", "logout(token)"]},
    ],
    "tech_choices": [
        {"technology": "PyJWT", "reason": "JWT token management"},
    ],
    "data_flow": "User sends credentials → API → AuthService → JWT token returned",
    "risks": ["Token storage security", "Rate limiting on login"],
})


def _make_context_with_pm() -> AgentContext:
    llm = MagicMock(spec=LLMClient)
    llm.chat.return_value = ChatResponse(content=SAMPLE_RESPONSE, model="deepseek-v4-pro", usage={})
    return AgentContext(
        intent=IntentDocument(feature="User auth"),
        config=Config(),
        llm_client=llm,
        upstream_artifacts={"pm": Artifact(
            stage="pm", summary="Reqs", structured_data={"user_stories": [{"id": "US-001", "title": "Login"}]}
        )},
    )


def test_architect_role():
    assert ArchitectAgent().role == AgentRole.ARCHITECT


def test_architect_produces_artifact():
    agent = ArchitectAgent()
    ctx = _make_context_with_pm()
    art = agent.execute(ctx)
    assert art.stage == "architect"
    assert "modules" in art.structured_data
    assert len(art.structured_data["modules"]) == 2


def test_architect_includes_interfaces_and_tech():
    agent = ArchitectAgent()
    ctx = _make_context_with_pm()
    art = agent.execute(ctx)
    assert "interfaces" in art.structured_data
    assert "tech_choices" in art.structured_data


def test_architect_requires_pm_artifact():
    agent = ArchitectAgent()
    llm = MagicMock(spec=LLMClient)
    ctx = AgentContext(
        intent=IntentDocument(feature="test"),
        config=Config(),
        llm_client=llm,
        upstream_artifacts={},
    )
    with pytest.raises(ValueError, match="PM artifact"):
        agent.execute(ctx)


def test_architect_summary():
    agent = ArchitectAgent()
    ctx = _make_context_with_pm()
    art = agent.execute(ctx)
    assert "2 modules" in art.summary
    assert "auth" in art.summary
