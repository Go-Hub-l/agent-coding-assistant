"""Tests for Coder Agent."""

import json
from unittest.mock import MagicMock

import pytest

from agent_assistant.config import Config
from agent_assistant.llm.client import ChatResponse, LLMClient
from agent_assistant.orchestrator.intent import IntentDocument
from agent_assistant.pipeline.agent import AgentRole
from agent_assistant.pipeline.artifact import Artifact
from agent_assistant.pipeline.context import AgentContext
from agent_assistant.agents.coder import CoderAgent


SAMPLE_RESPONSE = json.dumps({
    "files": [
        {"path": "src/auth.py", "content": "class AuthService:\n    def login(self, email, password):\n        pass\n", "description": "Auth service"},
        {"path": "src/api.py", "content": "from flask import Blueprint\napi = Blueprint('api', __name__)\n", "description": "API routes"},
    ],
    "implementation_notes": "Used Flask blueprints for modularity",
})


def _make_context_with_upstream() -> AgentContext:
    llm = MagicMock(spec=LLMClient)
    llm.chat.return_value = ChatResponse(content=SAMPLE_RESPONSE, model="deepseek-chat", usage={})
    return AgentContext(
        intent=IntentDocument(feature="User auth"),
        config=Config(),
        llm_client=llm,
        upstream_artifacts={
            "pm": Artifact(stage="pm", summary="Reqs", structured_data={"user_stories": []}),
            "architect": Artifact(stage="architect", summary="Arch", structured_data={"modules": [{"name": "auth"}]}),
        },
    )


def test_coder_role():
    assert CoderAgent().role == AgentRole.CODER


def test_coder_produces_artifact():
    agent = CoderAgent()
    ctx = _make_context_with_upstream()
    art = agent.execute(ctx)
    assert art.stage == "coder"
    assert "files" in art.structured_data
    assert len(art.structured_data["files"]) == 2


def test_coder_files_have_required_fields():
    agent = CoderAgent()
    ctx = _make_context_with_upstream()
    art = agent.execute(ctx)
    for f in art.structured_data["files"]:
        assert "path" in f
        assert "content" in f
        assert "description" in f


def test_coder_requires_architect_artifact():
    agent = CoderAgent()
    llm = MagicMock(spec=LLMClient)
    ctx = AgentContext(
        intent=IntentDocument(feature="test"),
        config=Config(),
        llm_client=llm,
        upstream_artifacts={},
    )
    with pytest.raises(ValueError, match="Architect artifact"):
        agent.execute(ctx)


def test_coder_includes_feedback_in_prompt():
    """When context has feedback, Coder includes it in the prompt."""
    agent = CoderAgent()
    ctx = _make_context_with_upstream()
    ctx.feedback = "Reviewer found: missing error handling in login"
    agent.execute(ctx)

    messages = ctx.llm_client.chat.call_args[0][0]
    feedback_msg = [m for m in messages if "Previous attempt" in m.content]
    assert len(feedback_msg) == 1


def test_coder_summary():
    agent = CoderAgent()
    ctx = _make_context_with_upstream()
    art = agent.execute(ctx)
    assert "2 files" in art.summary
