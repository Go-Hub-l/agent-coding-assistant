"""Tests for the intervention (checkpoint) system."""

from unittest.mock import MagicMock, patch

import pytest

from agent_assistant.pipeline.agent import Agent, AgentRole
from agent_assistant.pipeline.artifact import Artifact
from agent_assistant.config import Config
from agent_assistant.pipeline.intervention import (
    InterventionConfig,
    InterventionHandler,
    InterventionAction,
)
from agent_assistant.pipeline.pipeline import Pipeline
from agent_assistant.pipeline.session import Session
from agent_assistant.orchestrator.intent import IntentDocument
from agent_assistant.llm.client import LLMClient


def _make_agent(role: AgentRole) -> MagicMock:
    agent = MagicMock(spec=Agent)
    agent.role = role
    agent.name = role.value.capitalize()
    agent.execute.return_value = Artifact(
        stage=role.value, summary=f"{role.value} output",
        structured_data={"data": "test"},
    )
    return agent


# --- InterventionConfig tests ---

def test_intervention_config_all():
    config = InterventionConfig(stages="all")
    assert config.should_intervene("pm") is True
    assert config.should_intervene("reviewer") is True


def test_intervention_config_none():
    config = InterventionConfig(stages="none")
    assert config.should_intervene("pm") is False
    assert config.should_intervene("coder") is False


def test_intervention_config_specific_stages():
    config = InterventionConfig(stages=["pm", "architect"])
    assert config.should_intervene("pm") is True
    assert config.should_intervene("architect") is True
    assert config.should_intervene("coder") is False


def test_intervention_config_empty_list():
    config = InterventionConfig(stages=[])
    assert config.should_intervene("pm") is False


# --- InterventionHandler tests ---

def test_intervention_handler_approve():
    handler = InterventionHandler(
        config=InterventionConfig(stages=["pm"]),
        prompt_fn=lambda artifact: InterventionAction.APPROVE,
    )
    artifact = Artifact(stage="pm", summary="Test", structured_data={"data": "x"})
    result = handler.on_stage_complete(artifact)
    assert result is None  # None means continue


def test_intervention_handler_abort():
    handler = InterventionHandler(
        config=InterventionConfig(stages=["pm"]),
        prompt_fn=lambda artifact: InterventionAction.ABORT,
    )
    artifact = Artifact(stage="pm", summary="Test", structured_data={"data": "x"})
    with pytest.raises(Exception):
        handler.on_stage_complete(artifact)


def test_intervention_handler_modify():
    modified_artifact = Artifact(stage="pm", summary="Modified", structured_data={"data": "modified"})
    handler = InterventionHandler(
        config=InterventionConfig(stages=["pm"]),
        prompt_fn=lambda artifact: InterventionAction.MODIFY,
        modify_fn=lambda artifact: modified_artifact,
    )
    artifact = Artifact(stage="pm", summary="Original", structured_data={"data": "original"})
    result = handler.on_stage_complete(artifact)
    # Modify returns the modified artifact for the pipeline to use
    assert result is not None


def test_intervention_handler_skips_non_configured_stages():
    handler = InterventionHandler(
        config=InterventionConfig(stages=["pm"]),
        prompt_fn=lambda artifact: InterventionAction.ABORT,
    )
    artifact = Artifact(stage="coder", summary="Test", structured_data={"data": "x"})
    result = handler.on_stage_complete(artifact)
    assert result is None  # Auto-advance for non-configured stages


# --- Pipeline integration tests ---

def test_pipeline_with_intervention_auto_advance():
    """Non-configured stages auto-advance without pausing."""
    pm = _make_agent(AgentRole.PM)
    intent = IntentDocument(feature="Test")
    config = Config()
    llm = MagicMock(spec=LLMClient)
    session = Session()

    handler = InterventionHandler(
        config=InterventionConfig(stages="none"),
        prompt_fn=lambda artifact: InterventionAction.APPROVE,
    )

    pipeline = Pipeline(
        agents=[pm],
        config=config,
        llm_client=llm,
        session=session,
        on_stage_complete=handler.on_stage_complete,
    )
    pipeline.run(intent)

    assert session.status == "completed"


def test_pipeline_with_intervention_callback():
    """Intervention callback receives artifact at configured stages."""
    pm = _make_agent(AgentRole.PM)
    intent = IntentDocument(feature="Test")
    config = Config()
    llm = MagicMock(spec=LLMClient)
    session = Session()

    seen_artifacts = []
    handler = InterventionHandler(
        config=InterventionConfig(stages=["pm"]),
        prompt_fn=lambda artifact: (seen_artifacts.append(artifact), InterventionAction.APPROVE)[1],
    )

    pipeline = Pipeline(
        agents=[pm],
        config=config,
        llm_client=llm,
        session=session,
        on_stage_complete=handler.on_stage_complete,
    )
    pipeline.run(intent)

    assert len(seen_artifacts) == 1
    assert seen_artifacts[0].stage == "pm"
