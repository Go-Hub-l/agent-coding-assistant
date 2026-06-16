"""Pipeline — serial execution engine for agent stages with feedback loops."""

from __future__ import annotations

import json
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

    Supports optional feedback loops where a reviewer agent can trigger
    re-execution of a producer agent (e.g., Coder↔Reviewer).

    Also supports an optional intervention callback at each stage boundary.
    """

    def __init__(
        self,
        agents: list[Agent],
        config: Config,
        llm_client: LLMClient,
        session: Session,
        on_stage_complete: Callable[[Artifact], str | None] | None = None,
        feedback_loops: list[tuple[str, str]] | None = None,
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
            feedback_loops: Optional list of (producer_stage, reviewer_stage)
                tuples defining local feedback loops. When the reviewer
                produces a "changes_requested" verdict, the producer is
                re-run with the review feedback, then the reviewer re-runs.
        """
        self._agents = agents
        self._config = config
        self._llm_client = llm_client
        self._session = session
        self._on_stage_complete = on_stage_complete
        self._feedback_loops: dict[str, str] = {}
        if feedback_loops:
            for producer, reviewer in feedback_loops:
                self._feedback_loops[reviewer] = producer

    @property
    def session(self) -> Session:
        return self._session

    def _find_agent(self, stage: str) -> Agent | None:
        """Find an agent by its stage/role value."""
        for agent in self._agents:
            if agent.role.value == stage:
                return agent
        return None

    def _build_context(
        self,
        intent: IntentDocument,
        project_context: dict | None,
        feedback: str | None = None,
    ) -> AgentContext:
        """Build an AgentContext with the current session state."""
        return AgentContext(
            intent=intent,
            config=self._config,
            llm_client=self._llm_client,
            upstream_artifacts=dict(self._session.artifacts),
            project_context=project_context or {},
            feedback=feedback,
        )

    def _run_feedback_loop(
        self,
        producer: Agent,
        reviewer: Agent,
        intent: IntentDocument,
        project_context: dict | None,
    ) -> bool:
        """Run a feedback loop between a producer and reviewer.

        Returns True if the loop resolved successfully (approved),
        False if it needs escalation or hit a fundamental issue.
        """
        max_retries = self._config.max_feedback_retries

        for attempt in range(max_retries):
            # Build feedback from the latest review issues
            review_artifact = self._session.artifacts.get(reviewer.role.value)
            issues = review_artifact.structured_data.get("issues", [])
            feedback_text = json.dumps(issues, indent=2, ensure_ascii=False)

            self._session.record_feedback(
                from_stage=reviewer.role.value,
                to_stage=producer.role.value,
                message=f"Attempt {attempt + 1}/{max_retries}: {feedback_text}",
            )

            # Re-run the producer with feedback
            producer_context = self._build_context(intent, project_context, feedback=feedback_text)
            new_producer_artifact = producer.execute(producer_context)
            self._session.record_artifact(new_producer_artifact)

            if self._on_stage_complete is not None:
                self._on_stage_complete(new_producer_artifact)

            # Re-run the reviewer
            reviewer_context = self._build_context(intent, project_context)
            new_review_artifact = reviewer.execute(reviewer_context)
            self._session.record_artifact(new_review_artifact)

            if self._on_stage_complete is not None:
                self._on_stage_complete(new_review_artifact)

            verdict = new_review_artifact.structured_data.get("verdict", "")

            if verdict == "approved":
                return True
            elif verdict == "fundamental_issue":
                self._session.status = "fundamental_issue"
                return False

        # Exhausted retries — escalate
        self._session.status = "escalated"
        return False

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
            context = self._build_context(intent, project_context)

            artifact = agent.execute(context)
            self._session.record_artifact(artifact)

            # Invoke the intervention callback if provided
            if self._on_stage_complete is not None:
                feedback = self._on_stage_complete(artifact)
                if feedback:
                    self._session.record_feedback(
                        from_stage=artifact.stage,
                        to_stage=agent.role.value,
                        message=feedback,
                    )

            # Check if this agent is part of a feedback loop (as the reviewer)
            stage = agent.role.value
            if stage in self._feedback_loops:
                producer_stage = self._feedback_loops[stage]
                verdict = artifact.structured_data.get("verdict", "")

                if verdict == "fundamental_issue":
                    self._session.status = "fundamental_issue"
                    return self._session

                if verdict == "changes_requested":
                    producer = self._find_agent(producer_stage)
                    if producer is not None:
                        resolved = self._run_feedback_loop(
                            producer, agent, intent, project_context,
                        )
                        if not resolved:
                            return self._session

        self._session.status = "completed"
        return self._session
