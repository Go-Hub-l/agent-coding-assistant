"""Tests for artifact validation."""

import pytest

from agent_assistant.pipeline.agent import AgentRole
from agent_assistant.pipeline.artifact import Artifact
from agent_assistant.pipeline.validation import ArtifactValidator, ValidationResult


@pytest.fixture
def validator():
    return ArtifactValidator()


# --- Common checks ---


def test_valid_artifact_passes(validator):
    """A well-formed PM artifact passes validation."""
    art = Artifact(stage="pm", summary="Reqs", structured_data={
        "user_stories": [{"id": "US-001", "title": "Login", "description": "desc", "acceptance_criteria": ["c1"]}],
    })
    result = validator.validate(art, AgentRole.PM)
    assert result.is_valid


def test_empty_summary_fails(validator):
    """Empty summary fails validation."""
    art = Artifact(stage="pm", summary="", structured_data={"user_stories": [{}]})
    result = validator.validate(art, AgentRole.PM)
    assert not result.is_valid


def test_empty_structured_data_fails(validator):
    """Empty structured data fails validation."""
    art = Artifact(stage="pm", summary="ok", structured_data={})
    result = validator.validate(art, AgentRole.PM)
    assert not result.is_valid


# --- PM validation ---


def test_pm_missing_user_stories(validator):
    art = Artifact(stage="pm", summary="ok", structured_data={"other": "data"})
    result = validator.validate(art, AgentRole.PM)
    assert not result.is_valid
    assert any("user_stories" in e.field for e in result.errors)


def test_pm_empty_user_stories(validator):
    art = Artifact(stage="pm", summary="ok", structured_data={"user_stories": []})
    result = validator.validate(art, AgentRole.PM)
    assert not result.is_valid


def test_pm_story_missing_fields(validator):
    art = Artifact(stage="pm", summary="ok", structured_data={
        "user_stories": [{"id": "US-001"}],  # missing title, description, acceptance_criteria
    })
    result = validator.validate(art, AgentRole.PM)
    assert not result.is_valid
    assert len(result.errors) >= 3


# --- Architect validation ---


def test_architect_valid(validator):
    art = Artifact(stage="architect", summary="Arch", structured_data={
        "modules": [{"name": "auth", "purpose": "Auth"}],
        "interfaces": [],
        "tech_choices": [],
    })
    result = validator.validate(art, AgentRole.ARCHITECT)
    assert result.is_valid


def test_architect_missing_modules(validator):
    art = Artifact(stage="architect", summary="Arch", structured_data={
        "interfaces": [], "tech_choices": [],
    })
    result = validator.validate(art, AgentRole.ARCHITECT)
    assert not result.is_valid


def test_architect_module_missing_name(validator):
    art = Artifact(stage="architect", summary="Arch", structured_data={
        "modules": [{"purpose": "no name"}],
        "interfaces": [],
        "tech_choices": [],
    })
    result = validator.validate(art, AgentRole.ARCHITECT)
    assert not result.is_valid


# --- Coder validation ---


def test_coder_valid(validator):
    art = Artifact(stage="coder", summary="Code", structured_data={
        "files": [{"path": "src/main.py", "content": "print('hello')"}],
    })
    result = validator.validate(art, AgentRole.CODER)
    assert result.is_valid


def test_coder_file_missing_path(validator):
    art = Artifact(stage="coder", summary="Code", structured_data={
        "files": [{"content": "code"}],
    })
    result = validator.validate(art, AgentRole.CODER)
    assert not result.is_valid


# --- Reviewer validation ---


def test_reviewer_valid(validator):
    art = Artifact(stage="reviewer", summary="Review", structured_data={
        "issues": [], "verdict": "pass",
    })
    result = validator.validate(art, AgentRole.REVIEWER)
    assert result.is_valid


def test_reviewer_missing_verdict(validator):
    art = Artifact(stage="reviewer", summary="Review", structured_data={
        "issues": [],
    })
    result = validator.validate(art, AgentRole.REVIEWER)
    assert not result.is_valid


# --- Tester validation ---


def test_tester_valid(validator):
    art = Artifact(stage="tester", summary="Tests", structured_data={
        "test_files": [{"path": "test.py", "content": "code"}],
        "results": {"passed": 5, "failed": 0},
    })
    result = validator.validate(art, AgentRole.TESTER)
    assert result.is_valid


# --- Format errors ---


def test_validation_result_format_errors(validator):
    art = Artifact(stage="pm", summary="", structured_data={})
    result = validator.validate(art, AgentRole.PM)
    formatted = result.format_errors()
    assert "[summary]" in formatted
