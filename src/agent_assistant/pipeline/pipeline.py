"""Pipeline — serial execution engine for agent stages."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from agent_assistant.pipeline.agent import Agent
from agent_assistant.pipeline.context import AgentContext

if TYPE_CHECKING:
    from agent_assistant.config import Config
    from agent_assistant.llm.client import LLMClient
    from agent_assistant.orchestrator.intent import IntentDocument
    from agent_assistant.pipeline.artifact import Artifact
    from agent_assistant.pipeline.session import Session


class Pipeline:
    """Serial pipeline that executes agents in order, passing artifacts forward.

    Supports an optional intervention callback at each stage boundary.
    """

    def __init__(
        self,
        agents: list[Agent],
        config: Config,
        llm_client: LLMClient,
        session: Session,
        on_stage_complete: Callable[[Artifact], str | None] | None = None,
    ):
        """
        Args:
            agents: Ordered list of agents to execute.
            config: Application config.
            llm_client: LLM client for API calls.
            session: Session state tracker.
            on_stage_complete: Optional callback invoked after each stage.
                Receives the artifact. If it returns a string, that string
                is treated as user feedback and passed into the next agent's
                context. If it returns None, the pipeline continues normally.
        """
        self._agents = agents
        self._config = config
        self._llm_client = llm_client
        self._session = session
        self._on_stage_complete = on_stage_complete

    @property
    def session(self) -> Session:
        return self._session

    def run(self, intent: IntentDocument, project_context: dict | None = None) -> Session:
        """Execute the full pipeline.

        Args:
            intent: The confirmed intent document.
            project_context: Optional project context (for iteration mode).

        Returns:
            The session with all artifacts recorded.
        """
        self._session.intent = intent
        self._session.status = "running"

        for agent in self._agents:
            context = AgentContext(
                intent=intent,
                config=self._config,
                llm_client=self._llm_client,
                upstream_artifacts=dict(self._session.artifacts),
                project_context=project_context or {},
                feedback=None,
            )

            artifact = agent.execute(context)
            self._session.record_artifact(artifact)

            # Invoke the intervention callback if provided
            if self._on_stage_complete is not None:
                feedback = self._on_stage_complete(artifact)
                if feedback:
                    # Store feedback for the next agent to consume
                    self._session.record_feedback(
                        from_stage=artifact.stage,
                        to_stage=agent.role.value,
                        message=feedback,
                    )

        self._session.status = "completed"
        return self._session
