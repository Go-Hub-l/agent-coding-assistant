"""Tests for Tester Agent."""

import json
from unittest.mock import MagicMock

import pytest

from agent_assistant.config import Config
from agent_assistant.llm.client import ChatResponse, LLMClient
from agent_assistant.orchestrator.intent import IntentDocument
from agent_assistant.pipeline.agent import AgentRole
from agent_assistant.pipeline.artifact import Artifact
from agent_assistant.pipeline.context import AgentContext
from agent_assistant.agents.tester import TesterAgent


PASSED_RESPONSE = json.dumps({
    "test_files": [
        {"path": "tests/test_main.py", "content": "def test_main(): assert True", "description": "Basic test"},
    ],
    "results": {"total": 1, "passed": 1, "failed": 0, "failures": []},
    "verdict": "passed",
    "summary": "All 1 tests passed.",
})

FAILED_RESPONSE = json.dumps({
    "test_files": [
        {"path": "tests/test_auth.py", "content": "def test_login(): assert False", "description": "Login test"},
    ],
    "results": {
        "total": 2,
        "passed": 1,
        "failed": 1,
        "failures": [
            {"test": "test_login", "error": "AssertionError: expected True", "file": "tests/test_auth.py:3"},
        ],
    },
    "verdict": "failed",
    "summary": "1 of 2 tests failed.",
})


def _make_context_with_coder_and_reviewer(response_content: str) -> AgentContext:
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
            "reviewer": Artifact(
                stage="reviewer", summary="Approved",
                structured_data={"issues": [], "verdict": "approved"},
            ),
        },
    )


def test_tester_role():
    assert TesterAgent().role == AgentRole.TESTER


def test_tester_produces_artifact():
    agent = TesterAgent()
    ctx = _make_context_with_coder_and_reviewer(PASSED_RESPONSE)
    art = agent.execute(ctx)
    assert art.stage == "tester"
    assert "test_files" in art.structured_data
    assert "results" in art.structured_data


def test_tester_passed():
    agent = TesterAgent()
    ctx = _make_context_with_coder_and_reviewer(PASSED_RESPONSE)
    art = agent.execute(ctx)
    assert art.structured_data["verdict"] == "passed"
    assert art.structured_data["results"]["failed"] == 0


def test_tester_failed():
    agent = TesterAgent()
    ctx = _make_context_with_coder_and_reviewer(FAILED_RESPONSE)
    art = agent.execute(ctx)
    assert art.structured_data["verdict"] == "failed"
    assert art.structured_data["results"]["failed"] == 1
    assert len(art.structured_data["results"]["failures"]) == 1


def test_tester_requires_coder_artifact():
    agent = TesterAgent()
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


def test_tester_includes_feedback_in_prompt():
    agent = TesterAgent()
    ctx = _make_context_with_coder_and_reviewer(PASSED_RESPONSE)
    ctx.feedback = "Previous test failures: test_login raised TypeError"
    agent.execute(ctx)
    messages = ctx.llm_client.chat.call_args[0][0]
    feedback_msg = [m for m in messages if "Previous" in m.content]
    assert len(feedback_msg) > 0


def test_tester_summary():
    agent = TesterAgent()
    ctx = _make_context_with_coder_and_reviewer(FAILED_RESPONSE)
    art = agent.execute(ctx)
    assert "failed" in art.summary.lower() or "1" in art.summary
