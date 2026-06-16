"""Artifact — the output produced by each agent in the pipeline."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Artifact:
    """Output of a single agent stage.

    Attributes:
        stage: The lifecycle stage that produced this artifact.
        summary: Human-readable description shown to the user.
        structured_data: Machine-readable data consumed by downstream agents.
    """

    stage: str
    summary: str
    structured_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "summary": self.summary,
            "structured_data": self.structured_data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Artifact":
        return cls(
            stage=data["stage"],
            summary=data.get("summary", ""),
            structured_data=data.get("structured_data", {}),
        )
