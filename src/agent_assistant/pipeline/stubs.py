"""Stub agents for testing the pipeline without real LLM calls."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_assistant.pipeline.agent import Agent, AgentRole
from agent_assistant.pipeline.artifact import Artifact

if TYPE_CHECKING:
    from agent_assistant.pipeline.context import AgentContext


class StubPMAgent(Agent):
    """Stub PM agent that returns a hardcoded requirements artifact.

    Used to verify the pipeline engine works end-to-end before
    integrating the real LLM-powered PM agent.
    """

    def __init__(self) -> None:
        super().__init__(AgentRole.PM)

    def execute(self, context: AgentContext) -> Artifact:
        return Artifact(
            stage=self.role.value,
            summary="Stub PM: Generated sample requirements document.",
            structured_data={
                "user_stories": [
                    {
                        "id": "US-001",
                        "title": "Sample user story",
                        "description": f"As a user, I want the feature described: {context.intent.feature}",
                        "acceptance_criteria": ["Feature works as described"],
                    }
                ],
                "constraints": context.intent.constraints,
                "target_modules": context.intent.target_modules,
            },
        )
