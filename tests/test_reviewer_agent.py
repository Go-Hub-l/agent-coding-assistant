"""Tests for Reviewer Agent."""

import json
from unittest.mock import MagicMock

import pytest

from agent_assistant.config import Config
from agent_assistant.llm.client import ChatResponse, LLMClient
from agent_assistant.orchestrator.intent import IntentDocument
from agent_assistant.pipeline.agent import AgentRole
from agent_assistant.pipeline.artifact import Artifact
from agent_assistant.pipeline.context import AgentContext
from agent_assistant.agents.reviewer import ReviewerAgent


APPROVED_RESPONSE = json.dumps({
    "issues": [],
    "verdict": "approved",
    "summary": "Code looks clean, follows the architecture design.",
})

CHANGES_REQUESTED_RESPONSE = json.dumps({
    "issues": [
        {
            "severity": "major",
            "location": "src/auth.py:42",
            "description": "Password stored in plain text",
            "suggestion": "Use bcrypt to hash passwords before storage",
        },
        {
            "severity": "minor",
            "location": "src/api.py:10",
            "description": "Missing type hint on handler function",
            "suggestion": "Add type hints for request and response",
        },
    ],
    "verdict": "changes_requested",
    "summary": "Found 2 issues: 1 major, 1 minor.",
})

FUNDAMENTAL_RESPONSE = json.dumps({
    "issues": [
        {
            "severity": "critical",
            "location": "src/auth.py",
            "description": "Architecture does not support the required OAuth2 flow",
            "suggestion": "Redesign auth module to support OAuth2 provider pattern",
        },
    ],
    "verdict": "fundamental_issue",
    "summary": "Fundamental architecture issue prevents implementation.",
})


def _make_context_with_coder(response_content: str) -> AgentContext:
    llm = MagicMock(spec=LLMClient)
    llm.chat.return_value = ChatResponse(content=response_content, model="deepseek-v4-pro", usage={})
    return AgentContext(
        intent=IntentDocument(feature="User auth"),
        config=Config(),
        llm_client=llm,
        upstream_artifacts={
            "pm": Artifact(
                stage="pm", summary="Reqs",
                structured_data={"user_stories": [{"id": "US-001", "title": "Login"}]},
            ),
            "architect": Artifact(
                stage="architect", summary="Arch",
                structured_data={"modules": [{"name": "auth"}], "interfaces": [], "tech_choices": []},
            ),
            "coder": Artifact(
                stage="coder", summary="Code",
                structured_data={"files": [{"path": "src/auth.py", "content": "class Auth: pass"}]},
            ),
        },
    )


def test_reviewer_role():
    assert ReviewerAgent().role == AgentRole.REVIEWER


def test_reviewer_produces_artifact():
    agent = ReviewerAgent()
    ctx = _make_context_with_coder(APPROVED_RESPONSE)
    art = agent.execute(ctx)
    assert art.stage == "reviewer"
    assert "issues" in art.structured_data
    assert "verdict" in art.structured_data


def test_reviewer_approved():
    agent = ReviewerAgent()
    ctx = _make_context_with_coder(APPROVED_RESPONSE)
    art = agent.execute(ctx)
    assert art.structured_data["verdict"] == "approved"
    assert art.structured_data["issues"] == []


def test_reviewer_changes_requested():
    agent = ReviewerAgent()
    ctx = _make_context_with_coder(CHANGES_REQUESTED_RESPONSE)
    art = agent.execute(ctx)
    assert art.structured_data["verdict"] == "changes_requested"
    assert len(art.structured_data["issues"]) == 2
    assert art.structured_data["issues"][0]["severity"] == "major"


def test_reviewer_fundamental_issue():
    agent = ReviewerAgent()
    ctx = _make_context_with_coder(FUNDAMENTAL_RESPONSE)
    art = agent.execute(ctx)
    assert art.structured_data["verdict"] == "fundamental_issue"
    assert len(art.structured_data["issues"]) == 1


def test_reviewer_requires_coder_artifact():
    agent = ReviewerAgent()
    llm = MagicMock(spec=LLMClient)
    ctx = AgentContext(
        intent=IntentDocument(feature="test"),
        config=Config(),
        llm_client=llm,
        upstream_artifacts={
            "pm": Artifact(stage="pm", summary="Reqs", structured_data={"user_stories": []}),
            "architect": Artifact(stage="architect", summary="Arch", structured_data={"modules": []}),
        },
    )
    with pytest.raises(ValueError, match="Coder artifact"):
        agent.execute(ctx)


def test_reviewer_includes_feedback_in_prompt():
    agent = ReviewerAgent()
    ctx = _make_context_with_coder(APPROVED_RESPONSE)
    ctx.feedback = "Previous review: missing error handling"
    agent.execute(ctx)
    messages = ctx.llm_client.chat.call_args[0][0]
    feedback_msg = [m for m in messages if "Previous" in m.content]
    assert len(feedback_msg) > 0


def test_reviewer_summary():
    agent = ReviewerAgent()
    ctx = _make_context_with_coder(CHANGES_REQUESTED_RESPONSE)
    art = agent.execute(ctx)
    assert "2 issues" in art.summary or "changes_requested" in art.summary
