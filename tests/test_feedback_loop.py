"""Tests for the Coder-Reviewer feedback loop."""

import json
from unittest.mock import MagicMock

import pytest

from agent_assistant.config import Config
from agent_assistant.llm.client import ChatResponse, LLMClient
from agent_assistant.orchestrator.intent import IntentDocument
from agent_assistant.pipeline.agent import Agent, AgentRole
from agent_assistant.pipeline.artifact import Artifact
from agent_assistant.pipeline.context import AgentContext
from agent_assistant.pipeline.pipeline import Pipeline
from agent_assistant.pipeline.session import Session


def _make_coder_response():
    return json.dumps({
        "files": [{"path": "main.py", "content": "print('hello')", "description": "Main file"}],
        "implementation_notes": "Simple implementation",
    })


def _make_review_response(verdict, issues=None):
    return json.dumps({
        "issues": issues or [],
        "verdict": verdict,
        "summary": f"Review: {verdict}",
    })


def _make_mock_llm(responses):
    """Create a mock LLM that returns responses in sequence."""
    llm = MagicMock(spec=LLMClient)
    llm.chat.side_effect = [
        ChatResponse(content=r, model="deepseek-chat", usage={}) for r in responses
    ]
    return llm


def test_feedback_loop_approved_first_try():
    """When reviewer approves on first try, loop exits immediately."""
    coder = MagicMock(spec=Agent)
    coder.role = AgentRole.CODER
    coder.name = "Coder"
    coder.execute.return_value = Artifact(
        stage="coder", summary="Code", structured_data={"files": [{"path": "a.py", "content": "x"}]},
    )

    reviewer = MagicMock(spec=Agent)
    reviewer.role = AgentRole.REVIEWER
    reviewer.name = "Reviewer"
    reviewer.execute.return_value = Artifact(
        stage="reviewer", summary="Approved",
        structured_data={"issues": [], "verdict": "approved"},
    )

    pm = MagicMock(spec=Agent)
    pm.role = AgentRole.PM
    pm.name = "PM"
    pm.execute.return_value = Artifact(
        stage="pm", summary="Reqs", structured_data={"user_stories": []},
    )

    intent = IntentDocument(feature="Test feature")
    config = Config()
    llm = MagicMock(spec=LLMClient)
    session = Session()

    pipeline = Pipeline(
        agents=[pm, coder, reviewer],
        config=config,
        llm_client=llm,
        session=session,
        feedback_loops=[("coder", "reviewer")],
    )
    pipeline.run(intent)

    assert coder.execute.call_count == 1
    assert reviewer.execute.call_count == 1
    assert session.status == "completed"


def test_feedback_loop_retries_on_changes_requested():
    """When reviewer requests changes, coder re-runs with feedback."""
    coder = MagicMock(spec=Agent)
    coder.role = AgentRole.CODER
    coder.name = "Coder"
    coder.execute.return_value = Artifact(
        stage="coder", summary="Code", structured_data={"files": [{"path": "a.py", "content": "x"}]},
    )

    reviewer = MagicMock(spec=Agent)
    reviewer.role = AgentRole.REVIEWER
    reviewer.name = "Reviewer"
    reviewer.execute.side_effect = [
        Artifact(stage="reviewer", summary="Changes requested",
                 structured_data={"issues": [{"severity": "major", "description": "Bug"}], "verdict": "changes_requested"}),
        Artifact(stage="reviewer", summary="Approved",
                 structured_data={"issues": [], "verdict": "approved"}),
    ]

    intent = IntentDocument(feature="Test feature")
    config = Config()
    llm = MagicMock(spec=LLMClient)
    session = Session()

    pipeline = Pipeline(
        agents=[coder, reviewer],
        config=config,
        llm_client=llm,
        session=session,
        feedback_loops=[("coder", "reviewer")],
    )
    pipeline.run(intent)

    assert coder.execute.call_count == 2
    assert reviewer.execute.call_count == 2
    # Second coder call should have feedback in context
    second_call_context = coder.execute.call_args_list[1][0][0]
    assert second_call_context.feedback is not None


def test_feedback_loop_respects_max_retries():
    """Loop stops after max_feedback_retries and escalates."""
    coder = MagicMock(spec=Agent)
    coder.role = AgentRole.CODER
    coder.name = "Coder"
    coder.execute.return_value = Artifact(
        stage="coder", summary="Code", structured_data={"files": [{"path": "a.py", "content": "x"}]},
    )

    reviewer = MagicMock(spec=Agent)
    reviewer.role = AgentRole.REVIEWER
    reviewer.name = "Reviewer"
    reviewer.execute.return_value = Artifact(
        stage="reviewer", summary="Changes requested",
        structured_data={"issues": [{"severity": "major", "description": "Bug"}], "verdict": "changes_requested"},
    )

    intent = IntentDocument(feature="Test feature")
    config = Config()
    config.max_feedback_retries = 3
    llm = MagicMock(spec=LLMClient)
    session = Session()

    pipeline = Pipeline(
        agents=[coder, reviewer],
        config=config,
        llm_client=llm,
        session=session,
        feedback_loops=[("coder", "reviewer")],
    )
    pipeline.run(intent)

    # 1 initial + 3 retries = 4 coder calls
    assert coder.execute.call_count == 4
    assert reviewer.execute.call_count == 4
    assert session.status == "escalated"


def test_feedback_loop_fundamental_issue_stops_pipeline():
    """Fundamental issue verdict stops the pipeline immediately."""
    coder = MagicMock(spec=Agent)
    coder.role = AgentRole.CODER
    coder.name = "Coder"
    coder.execute.return_value = Artifact(
        stage="coder", summary="Code", structured_data={"files": [{"path": "a.py", "content": "x"}]},
    )

    reviewer = MagicMock(spec=Agent)
    reviewer.role = AgentRole.REVIEWER
    reviewer.name = "Reviewer"
    reviewer.execute.return_value = Artifact(
        stage="reviewer", summary="Fundamental issue",
        structured_data={"issues": [{"severity": "critical", "description": "Bad arch"}], "verdict": "fundamental_issue"},
    )

    intent = IntentDocument(feature="Test feature")
    config = Config()
    llm = MagicMock(spec=LLMClient)
    session = Session()

    pipeline = Pipeline(
        agents=[coder, reviewer],
        config=config,
        llm_client=llm,
        session=session,
        feedback_loops=[("coder", "reviewer")],
    )
    pipeline.run(intent)

    assert coder.execute.call_count == 1
    assert reviewer.execute.call_count == 1
    assert session.status == "fundamental_issue"


def test_feedback_loop_records_feedback_in_session():
    """Feedback loop events are recorded in session feedback_log."""
    coder = MagicMock(spec=Agent)
    coder.role = AgentRole.CODER
    coder.name = "Coder"
    coder.execute.return_value = Artifact(
        stage="coder", summary="Code", structured_data={"files": [{"path": "a.py", "content": "x"}]},
    )

    reviewer = MagicMock(spec=Agent)
    reviewer.role = AgentRole.REVIEWER
    reviewer.name = "Reviewer"
    reviewer.execute.side_effect = [
        Artifact(stage="reviewer", summary="Changes",
                 structured_data={"issues": [{"severity": "major", "description": "Fix"}], "verdict": "changes_requested"}),
        Artifact(stage="reviewer", summary="OK",
                 structured_data={"issues": [], "verdict": "approved"}),
    ]

    intent = IntentDocument(feature="Test")
    config = Config()
    llm = MagicMock(spec=LLMClient)
    session = Session()

    pipeline = Pipeline(
        agents=[coder, reviewer],
        config=config,
        llm_client=llm,
        session=session,
        feedback_loops=[("coder", "reviewer")],
    )
    pipeline.run(intent)

    assert len(session.feedback_log) >= 1
    assert session.feedback_log[0]["from"] == "reviewer"
    assert session.feedback_log[0]["to"] == "coder"


def test_pipeline_without_feedback_loops_works_as_before():
    """Pipeline without feedback_loops parameter works like the old serial pipeline."""
    pm = MagicMock(spec=Agent)
    pm.role = AgentRole.PM
    pm.name = "PM"
    pm.execute.return_value = Artifact(
        stage="pm", summary="Reqs", structured_data={"user_stories": []},
    )

    intent = IntentDocument(feature="Test")
    config = Config()
    llm = MagicMock(spec=LLMClient)
    session = Session()

    pipeline = Pipeline(
        agents=[pm],
        config=config,
        llm_client=llm,
        session=session,
    )
    pipeline.run(intent)

    assert session.status == "completed"
    assert pm.execute.call_count == 1


def test_tester_feedback_loop_retries_on_failure():
    """When tester reports failures, coder re-runs with failure details."""
    coder = MagicMock(spec=Agent)
    coder.role = AgentRole.CODER
    coder.name = "Coder"
    coder.execute.return_value = Artifact(
        stage="coder", summary="Code", structured_data={"files": [{"path": "a.py", "content": "x"}]},
    )

    tester = MagicMock(spec=Agent)
    tester.role = AgentRole.TESTER
    tester.name = "Tester"
    tester.execute.side_effect = [
        Artifact(stage="tester", summary="Tests failed",
                 structured_data={
                     "test_files": [{"path": "tests/test_a.py", "content": "test"}],
                     "results": {"total": 2, "passed": 1, "failed": 1,
                                 "failures": [{"test": "test_login", "error": "AssertionError"}]},
                     "verdict": "failed",
                 }),
        Artifact(stage="tester", summary="Tests passed",
                 structured_data={
                     "test_files": [{"path": "tests/test_a.py", "content": "test"}],
                     "results": {"total": 2, "passed": 2, "failed": 0, "failures": []},
                     "verdict": "passed",
                 }),
    ]

    intent = IntentDocument(feature="Test feature")
    config = Config()
    llm = MagicMock(spec=LLMClient)
    session = Session()

    pipeline = Pipeline(
        agents=[coder, tester],
        config=config,
        llm_client=llm,
        session=session,
        feedback_loops=[("coder", "tester")],
    )
    pipeline.run(intent)

    assert coder.execute.call_count == 2
    assert tester.execute.call_count == 2
    # Verify feedback was passed to the coder on retry
    second_call_context = coder.execute.call_args_list[1][0][0]
    assert second_call_context.feedback is not None


def test_tester_feedback_loop_max_retries_escalates():
    """Tester feedback loop escalates when max retries exhausted."""
    coder = MagicMock(spec=Agent)
    coder.role = AgentRole.CODER
    coder.name = "Coder"
    coder.execute.return_value = Artifact(
        stage="coder", summary="Code", structured_data={"files": [{"path": "a.py", "content": "x"}]},
    )

    tester = MagicMock(spec=Agent)
    tester.role = AgentRole.TESTER
    tester.name = "Tester"
    tester.execute.return_value = Artifact(
        stage="tester", summary="Tests failed",
        structured_data={
            "test_files": [{"path": "tests/test_a.py", "content": "test"}],
            "results": {"total": 2, "passed": 1, "failed": 1,
                        "failures": [{"test": "test_login", "error": "AssertionError"}]},
            "verdict": "failed",
        },
    )

    intent = IntentDocument(feature="Test feature")
    config = Config()
    config.max_feedback_retries = 2
    llm = MagicMock(spec=LLMClient)
    session = Session()

    pipeline = Pipeline(
        agents=[coder, tester],
        config=config,
        llm_client=llm,
        session=session,
        feedback_loops=[("coder", "tester")],
    )
    pipeline.run(intent)

    assert coder.execute.call_count == 3  # 1 initial + 2 retries
    assert tester.execute.call_count == 3
    assert session.status == "escalated"
