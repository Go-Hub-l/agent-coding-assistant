"""Session — in-memory state for a single pipeline run."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_assistant.orchestrator.intent import IntentDocument
    from agent_assistant.pipeline.artifact import Artifact


@dataclass
class Session:
    """In-memory state for one pipeline execution.

    Tracks the confirmed intent, all produced artifacts, pipeline progress,
    and feedback loop history. State is discarded when the session ends.
    """

    intent: IntentDocument | None = None
    artifacts: dict[str, Artifact] = field(default_factory=dict)
    completed_stages: list[str] = field(default_factory=list)
    feedback_log: list[dict] = field(default_factory=list)
    status: str = "idle"  # idle | running | paused | completed | failed

    def record_artifact(self, artifact: Artifact) -> None:
        """Store an artifact and mark the stage as completed."""
        self.artifacts[artifact.stage] = artifact
        if artifact.stage not in self.completed_stages:
            self.completed_stages.append(artifact.stage)

    def record_feedback(self, from_stage: str, to_stage: str, message: str) -> None:
        """Record a feedback loop event."""
        self.feedback_log.append({
            "from": from_stage,
            "to": to_stage,
            "message": message,
        })

    def reset(self) -> None:
        """Reset session to initial state."""
        self.intent = None
        self.artifacts.clear()
        self.completed_stages.clear()
        self.feedback_log.clear()
        self.status = "idle"
