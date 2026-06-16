"""Agent base class and role definitions."""

from __future__ import annotations

import abc
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_assistant.pipeline.artifact import Artifact
    from agent_assistant.pipeline.context import AgentContext


class AgentRole(str, Enum):
    """The five lifecycle agent roles."""

    PM = "pm"
    ARCHITECT = "architect"
    CODER = "coder"
    REVIEWER = "reviewer"
    TESTER = "tester"


class Agent(abc.ABC):
    """Abstract base class for all pipeline agents."""

    def __init__(self, role: AgentRole):
        self.role = role

    @property
    def name(self) -> str:
        return self.role.value.capitalize()

    @abc.abstractmethod
    def execute(self, context: AgentContext) -> Artifact:
        """Execute this agent's task given the current context.

        Args:
            context: Contains intent, upstream artifacts, project context,
                     and LLM client.

        Returns:
            An Artifact containing this stage's output.
        """
        ...
