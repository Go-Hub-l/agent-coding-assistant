"""Tests for pipeline engine, session, and stub agents."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent_assistant.config import Config
from agent_assistant.llm.client import LLMClient
from agent_assistant.orchestrator.intent import IntentDocument
from agent_assistant.pipeline.agent import Agent, AgentRole
from agent_assistant.pipeline.artifact import Artifact
from agent_assistant.pipeline.context import AgentContext
from agent_assistant.pipeline.pipeline import Pipeline
from agent_assistant.pipeline.session import Session
from agent_assistant.pipeline.stubs import StubPMAgent


# --- Artifact tests ---


def test_artifact_creation():
    """Artifact stores stage, summary, and structured data."""
    art = Artifact(stage="pm", summary="Test", structured_data={"key": "value"})
    assert art.stage == "pm"
    assert art.summary == "Test"
    assert art.structured_data["key"] == "value"


def test_artifact_serialization():
    """Artifact round-trips through to_dict / from_dict."""
    art = Artifact(stage="pm", summary="Test", structured_data={"x": 1})
    data = art.to_dict()
    restored = Artifact.from_dict(data)
    assert restored.stage == art.stage
    assert restored.summary == art.summary
    assert restored.structured_data == art.structured_data


def test_artifact_default_structured_data():
    """Artifact structured_data defaults to empty dict."""
    art = Artifact(stage="pm", summary="Test")
    assert art.structured_data == {}


# --- Session tests ---


def test_session_initial_state():
    """Session starts with idle status and empty state."""
    session = Session()
    assert session.status == "idle"
    assert session.artifacts == {}
    assert session.completed_stages == []


def test_session_record_artifact():
    """Session records artifacts and tracks completed stages."""
    session = Session()
    art = Artifact(stage="pm", summary="Requirements")
    session.record_artifact(art)
    assert "pm" in session.artifacts
    assert "pm" in session.completed_stages


def test_session_record_feedback():
    """Session records feedback loop events."""
    session = Session()
    session.record_feedback("reviewer", "coder", "Fix naming")
    assert len(session.feedback_log) == 1
    assert session.feedback_log[0]["from"] == "reviewer"


def test_session_reset():
    """Session.reset clears all state."""
    session = Session()
    session.record_artifact(Artifact(stage="pm", summary="Test"))
    session.status = "running"
    session.reset()
    assert session.status == "idle"
    assert session.artifacts == {}
    assert session.completed_stages == []


# --- AgentContext tests ---


def test_agent_context_get_upstream_artifact():
    """AgentContext can retrieve upstream artifacts by stage name."""
    art = Artifact(stage="pm", summary="Reqs")
    ctx = AgentContext(
        intent=IntentDocument(feature="test"),
        config=Config(),
        llm_client=MagicMock(spec=LLMClient),
        upstream_artifacts={"pm": art},
    )
    assert ctx.get_upstream_artifact("pm") is art
    assert ctx.get_upstream_artifact("architect") is None


# --- StubPMAgent tests ---


def test_stub_pm_agent_execute():
    """StubPMAgent returns a valid artifact with intent data."""
    agent = StubPMAgent()
    assert agent.role == AgentRole.PM
    assert agent.name == "Pm"

    ctx = AgentContext(
        intent=IntentDocument(
            feature="User login",
            constraints=["JWT"],
            target_modules=["auth"],
        ),
        config=Config(),
        llm_client=MagicMock(spec=LLMClient),
    )

    art = agent.execute(ctx)
    assert art.stage == "pm"
    assert art.summary  # not empty
    assert "user_stories" in art.structured_data
    assert art.structured_data["constraints"] == ["JWT"]


# --- Pipeline tests ---


def _make_config_and_llm():
    config = Config(api_key="test")
    llm = MagicMock(spec=LLMClient)
    return config, llm


def test_pipeline_runs_single_agent():
    """Pipeline executes a single stub agent end-to-end."""
    config, llm = _make_config_and_llm()
    session = Session()
    pipeline = Pipeline(
        agents=[StubPMAgent()],
        config=config,
        llm_client=llm,
        session=session,
    )

    intent = IntentDocument(feature="User login")
    result = pipeline.run(intent)

    assert result.status == "completed"
    assert "pm" in result.artifacts
    assert result.artifacts["pm"].stage == "pm"
    assert result.intent is intent


def test_pipeline_passes_upstream_artifacts():
    """Pipeline passes artifacts from earlier stages to later agents."""

    class RecordingAgent(Agent):
        """Agent that records what context it received."""

        def __init__(self, role: AgentRole):
            super().__init__(role)
            self.received_context = None

        def execute(self, context: AgentContext) -> Artifact:
            self.received_context = context
            return Artifact(stage=self.role.value, summary="done")

    config, llm = _make_config_and_llm()
    session = Session()

    recorder = RecordingAgent(AgentRole.ARCHITECT)
    pipeline = Pipeline(
        agents=[StubPMAgent(), recorder],
        config=config,
        llm_client=llm,
        session=session,
    )

    pipeline.run(IntentDocument(feature="test"))

    # Architect should see PM's artifact in upstream
    assert recorder.received_context is not None
    pm_art = recorder.received_context.get_upstream_artifact("pm")
    assert pm_art is not None
    assert pm_art.stage == "pm"


def test_pipeline_invokes_callback():
    """Pipeline calls on_stage_complete after each agent."""
    config, llm = _make_config_and_llm()
    session = Session()
    callback_artifacts = []

    def callback(artifact):
        callback_artifacts.append(artifact)
        return None  # no feedback

    pipeline = Pipeline(
        agents=[StubPMAgent()],
        config=config,
        llm_client=llm,
        session=session,
        on_stage_complete=callback,
    )

    pipeline.run(IntentDocument(feature="test"))

    assert len(callback_artifacts) == 1
    assert callback_artifacts[0].stage == "pm"


def test_pipeline_tracks_completed_stages_in_order():
    """Session.completed_stages lists stages in execution order."""
    config, llm = _make_config_and_llm()
    session = Session()

    class SimpleAgent(Agent):
        def execute(self, context):
            return Artifact(stage=self.role.value, summary="ok")

    agents = [
        StubPMAgent(),
        SimpleAgent(AgentRole.ARCHITECT),
    ]
    pipeline = Pipeline(agents=agents, config=config, llm_client=llm, session=session)
    pipeline.run(IntentDocument(feature="test"))

    assert session.completed_stages == ["pm", "architect"]
