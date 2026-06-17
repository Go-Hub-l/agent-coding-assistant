"""Tests for PM Agent."""

import json
from unittest.mock import MagicMock

import pytest

from agent_assistant.config import Config
from agent_assistant.llm.client import ChatResponse, LLMClient
from agent_assistant.orchestrator.intent import IntentDocument
from agent_assistant.pipeline.agent import AgentRole
from agent_assistant.pipeline.artifact import Artifact
from agent_assistant.pipeline.context import AgentContext
from agent_assistant.agents.pm import PMAgent


SAMPLE_LLM_RESPONSE = json.dumps({
    "user_stories": [
        {
            "id": "US-001",
            "title": "User can log in",
            "description": "As a user, I want to log in with email and password, so that I can access my account",
            "acceptance_criteria": [
                "Valid credentials return a JWT token",
                "Invalid credentials return 401",
            ],
            "priority": "high",
        },
        {
            "id": "US-002",
            "title": "User can log out",
            "description": "As a user, I want to log out, so that my session is terminated",
            "acceptance_criteria": [
                "Logout endpoint invalidates the token",
                "Returns 200 OK",
            ],
            "priority": "medium",
        },
    ],
    "dependencies": ["bcrypt", "PyJWT"],
    "non_functional_requirements": ["Tokens expire after 24 hours"],
    "out_of_scope": ["Third-party OAuth", "Multi-factor authentication"],
})


def _make_context(feature: str = "User login", **kwargs) -> AgentContext:
    llm = MagicMock(spec=LLMClient)
    llm.chat.return_value = ChatResponse(
        content=SAMPLE_LLM_RESPONSE, model="deepseek-v4-pro", usage={}
    )
    return AgentContext(
        intent=IntentDocument(feature=feature, **kwargs),
        config=Config(),
        llm_client=llm,
    )


def test_pm_agent_role():
    """PMAgent has the PM role."""
    agent = PMAgent()
    assert agent.role == AgentRole.PM
    assert agent.name == "Pm"


def test_pm_agent_produces_artifact():
    """PMAgent produces an artifact with structured requirements."""
    agent = PMAgent()
    ctx = _make_context()
    art = agent.execute(ctx)

    assert isinstance(art, Artifact)
    assert art.stage == "pm"
    assert art.summary  # not empty
    assert "user_stories" in art.structured_data
    assert len(art.structured_data["user_stories"]) == 2


def test_pm_agent_user_stories_have_required_fields():
    """Each user story has id, title, description, acceptance_criteria, priority."""
    agent = PMAgent()
    ctx = _make_context()
    art = agent.execute(ctx)

    for story in art.structured_data["user_stories"]:
        assert "id" in story
        assert "title" in story
        assert "description" in story
        assert "acceptance_criteria" in story
        assert len(story["acceptance_criteria"]) >= 1
        assert "priority" in story


def test_pm_agent_summary_lists_stories():
    """PMAgent summary mentions the user stories."""
    agent = PMAgent()
    ctx = _make_context()
    art = agent.execute(ctx)

    assert "2 user stories" in art.summary
    assert "User can log in" in art.summary


def test_pm_agent_includes_constraints_in_prompt():
    """PMAgent includes intent constraints in the LLM prompt."""
    agent = PMAgent()
    ctx = _make_context(constraints=["Use JWT"], target_modules=["auth"])
    agent.execute(ctx)

    messages = ctx.llm_client.chat.call_args[0][0]
    user_msg = messages[1].content
    assert "Use JWT" in user_msg
    assert "auth" in user_msg


def test_pm_agent_includes_project_context():
    """PMAgent includes project context when available."""
    agent = PMAgent()
    ctx = _make_context()
    ctx.project_context = {"summary": "Flask app with SQLAlchemy"}
    agent.execute(ctx)

    messages = ctx.llm_client.chat.call_args[0][0]
    user_msg = messages[1].content
    assert "Flask app" in user_msg


def test_pm_agent_handles_markdown_fences():
    """PMAgent handles LLM responses wrapped in markdown code fences."""
    agent = PMAgent()
    ctx = _make_context()
    ctx.llm_client.chat.return_value = ChatResponse(
        content=f"```json\n{SAMPLE_LLM_RESPONSE}\n```",
        model="deepseek-v4-pro",
        usage={},
    )
    art = agent.execute(ctx)
    assert len(art.structured_data["user_stories"]) == 2


def test_pm_agent_invalid_json_raises():
    """PMAgent raises when LLM returns invalid JSON."""
    agent = PMAgent()
    ctx = _make_context()
    ctx.llm_client.chat.return_value = ChatResponse(
        content="This is not JSON",
        model="deepseek-v4-pro",
        usage={},
    )
    with pytest.raises(json.JSONDecodeError):
        agent.execute(ctx)
