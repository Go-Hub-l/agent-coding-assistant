"""Intervention system — user-selectable checkpoints at stage boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Callable

import typer

if TYPE_CHECKING:
    from agent_assistant.pipeline.artifact import Artifact


class InterventionAction(str, Enum):
    """Possible user actions at a checkpoint."""

    APPROVE = "approve"
    MODIFY = "modify"
    ABORT = "abort"


@dataclass
class InterventionConfig:
    """Configuration for which stage boundaries to pause at.

    Args:
        stages: "all" to pause at every stage, "none" to never pause,
                or a list of specific stage names (e.g., ["pm", "coder"]).
    """

    stages: str | list[str] = "none"

    def should_intervene(self, stage: str) -> bool:
        """Check if the pipeline should pause at the given stage."""
        if self.stages == "all":
            return True
        if self.stages == "none" or self.stages is None:
            return False
        if isinstance(self.stages, list):
            return stage in self.stages
        return False


@dataclass
class InterventionHandler:
    """Handles intervention callbacks at stage boundaries.

    Uses pluggable prompt and modify functions for testability.
    In production, prompt_fn displays the artifact via Rich/Typer
    and asks the user what to do. For tests, it's a simple lambda.

    Args:
        config: Which stages to intervene at.
        prompt_fn: Called with the artifact to ask what action to take.
                   Returns an InterventionAction.
        modify_fn: Called when user chooses MODIFY. Receives the artifact
                   and returns a modified artifact.
    """

    config: InterventionConfig = field(default_factory=InterventionConfig)
    prompt_fn: Callable[[Artifact], InterventionAction] = lambda _: InterventionAction.APPROVE
    modify_fn: Callable[[Artifact], Artifact] | None = None

    def on_stage_complete(self, artifact: Artifact) -> str | None:
        """Callback invoked by the Pipeline after each stage completes.

        Returns None to continue the pipeline, or a feedback string
        if the user chose to modify the artifact.
        """
        if not self.config.should_intervene(artifact.stage):
            return None

        action = self.prompt_fn(artifact)

        if action == InterventionAction.APPROVE:
            return None
        elif action == InterventionAction.ABORT:
            raise typer.Abort()
        elif action == InterventionAction.MODIFY:
            if self.modify_fn is not None:
                modified = self.modify_fn(artifact)
                # Return a signal that the pipeline can use to update
                return f"__modified__:{modified.stage}"
            return None

        return None
