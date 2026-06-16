"""Artifact validation — schema checks for each agent role's output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_assistant.pipeline.artifact import Artifact
from agent_assistant.pipeline.agent import AgentRole


@dataclass
class ValidationError:
    """A single validation issue found in an artifact."""

    field: str
    message: str


@dataclass
class ValidationResult:
    """Result of validating an artifact."""

    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)

    def format_errors(self) -> str:
        if not self.errors:
            return "No errors"
        lines = []
        for e in self.errors:
            lines.append(f"- [{e.field}] {e.message}")
        return "\n".join(lines)


class ArtifactValidator:
    """Validates artifacts against role-specific schemas."""

    def validate(self, artifact: Artifact, role: AgentRole) -> ValidationResult:
        """Validate an artifact for a given agent role."""
        errors: list[ValidationError] = []

        # Common checks
        if not artifact.summary:
            errors.append(ValidationError("summary", "Summary must not be empty"))
        if not artifact.structured_data:
            errors.append(ValidationError("structured_data", "Structured data must not be empty"))

        # Role-specific checks
        validator = getattr(self, f"_validate_{role.value}", None)
        if validator:
            errors.extend(validator(artifact.structured_data))

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def _validate_pm(self, data: dict[str, Any]) -> list[ValidationError]:
        errors = []
        if "user_stories" not in data:
            errors.append(ValidationError("user_stories", "Missing required field"))
        elif not isinstance(data["user_stories"], list):
            errors.append(ValidationError("user_stories", "Must be a list"))
        elif len(data["user_stories"]) == 0:
            errors.append(ValidationError("user_stories", "Must contain at least one story"))
        else:
            for i, story in enumerate(data["user_stories"]):
                if not isinstance(story, dict):
                    errors.append(ValidationError(f"user_stories[{i}]", "Must be an object"))
                    continue
                for required in ("id", "title", "description", "acceptance_criteria"):
                    if required not in story:
                        errors.append(ValidationError(f"user_stories[{i}].{required}", f"Missing required field"))
        return errors

    def _validate_architect(self, data: dict[str, Any]) -> list[ValidationError]:
        errors = []
        if "modules" not in data:
            errors.append(ValidationError("modules", "Missing required field"))
        elif not isinstance(data["modules"], list) or len(data["modules"]) == 0:
            errors.append(ValidationError("modules", "Must be a non-empty list"))
        else:
            for i, mod in enumerate(data["modules"]):
                if not isinstance(mod, dict):
                    errors.append(ValidationError(f"modules[{i}]", "Must be an object"))
                    continue
                if "name" not in mod:
                    errors.append(ValidationError(f"modules[{i}].name", "Missing required field"))
        if "interfaces" not in data:
            errors.append(ValidationError("interfaces", "Missing required field"))
        if "tech_choices" not in data:
            errors.append(ValidationError("tech_choices", "Missing required field"))
        return errors

    def _validate_coder(self, data: dict[str, Any]) -> list[ValidationError]:
        errors = []
        if "files" not in data:
            errors.append(ValidationError("files", "Missing required field"))
        elif not isinstance(data["files"], list) or len(data["files"]) == 0:
            errors.append(ValidationError("files", "Must be a non-empty list"))
        else:
            for i, f in enumerate(data["files"]):
                if not isinstance(f, dict):
                    errors.append(ValidationError(f"files[{i}]", "Must be an object"))
                    continue
                for required in ("path", "content"):
                    if required not in f:
                        errors.append(ValidationError(f"files[{i}].{required}", "Missing required field"))
        return errors

    def _validate_reviewer(self, data: dict[str, Any]) -> list[ValidationError]:
        errors = []
        if "issues" not in data:
            errors.append(ValidationError("issues", "Missing required field"))
        elif not isinstance(data["issues"], list):
            errors.append(ValidationError("issues", "Must be a list"))
        if "verdict" not in data:
            errors.append(ValidationError("verdict", "Missing required field"))
        return errors

    def _validate_tester(self, data: dict[str, Any]) -> list[ValidationError]:
        errors = []
        if "test_files" not in data:
            errors.append(ValidationError("test_files", "Missing required field"))
        elif not isinstance(data["test_files"], list):
            errors.append(ValidationError("test_files", "Must be a list"))
        if "results" not in data:
            errors.append(ValidationError("results", "Missing required field"))
        return errors
