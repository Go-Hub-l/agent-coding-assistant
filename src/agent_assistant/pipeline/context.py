"""AgentContext — the information passed to each agent during execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent_assistant.config import Config
    from agent_assistant.llm.client import LLMClient
    from agent_assistant.orchestrator.intent import IntentDocument
    from agent_assistant.pipeline.artifact import Artifact


@dataclass
class AgentContext:
    """Context passed to each agent during pipeline execution.

    Carries the original intent, all upstream artifacts, project context,
    and the LLM client for making API calls.
    """

    intent: IntentDocument
    config: Config
    llm_client: LLMClient
    upstream_artifacts: dict[str, Artifact] = field(default_factory=dict)
    project_context: dict[str, Any] = field(default_factory=dict)
    feedback: str | None = None  # feedback from a previous review/test cycle

    def get_upstream_artifact(self, stage: str) -> Artifact | None:
        """Retrieve an artifact from a previous stage."""
        return self.upstream_artifacts.get(stage)
