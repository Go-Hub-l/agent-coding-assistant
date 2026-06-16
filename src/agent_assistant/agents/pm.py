"""PM Agent — requirements analysis stage."""

from __future__ import annotations

import json
from typing import Any

from agent_assistant.llm.client import ChatMessage
from agent_assistant.pipeline.agent import Agent, AgentRole
from agent_assistant.pipeline.artifact import Artifact
from agent_assistant.pipeline.context import AgentContext

PM_SYSTEM_PROMPT = """\
You are a senior Product Manager specializing in software requirements analysis. \
Your job is to produce clear, actionable requirements from a developer's intent.

Given a feature description, produce a structured requirements document.

Output ONLY valid JSON with this schema (no markdown fences, no commentary):

{
  "user_stories": [
    {
      "id": "US-001",
      "title": "Short title",
      "description": "As a <user>, I want <goal>, so that <benefit>",
      "acceptance_criteria": ["Criterion 1", "Criterion 2"],
      "priority": "high | medium | low"
    }
  ],
  "dependencies": ["List of external dependencies or preconditions"],
  "non_functional_requirements": ["Performance, security, scalability requirements"],
  "out_of_scope": ["Things explicitly NOT included"]
}

Rules:
- Break features into 2-6 user stories depending on scope.
- Each story must have at least 2 acceptance criteria.
- Be specific — avoid vague terms like "user-friendly" or "fast".
- Include dependencies if the feature needs external libraries or services.
- List non-functional requirements (security, performance) when relevant.
"""


def _extract_json(text: str) -> str:
    """Extract JSON from LLM response."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)
    return text.strip()


class PMAgent(Agent):
    """PM agent that produces structured requirements from the intent."""

    def __init__(self) -> None:
        super().__init__(AgentRole.PM)

    def execute(self, context: AgentContext) -> Artifact:
        """Analyze the intent and produce a requirements artifact."""
        user_prompt = self._build_prompt(context)

        messages = [
            ChatMessage(role="system", content=PM_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ]

        response = context.llm_client.chat(messages)
        raw_json = _extract_json(response.content)
        data = json.loads(raw_json)

        summary = self._build_summary(data)

        return Artifact(
            stage=self.role.value,
            summary=summary,
            structured_data=data,
        )

    def _build_prompt(self, context: AgentContext) -> str:
        """Build the user prompt with intent and project context."""
        parts = [f"Feature request: {context.intent.feature}"]

        if context.intent.constraints:
            parts.append(f"Constraints: {', '.join(context.intent.constraints)}")
        if context.intent.target_modules:
            parts.append(f"Target modules: {', '.join(context.intent.target_modules)}")
        if context.intent.assumptions:
            parts.append(f"Assumptions: {', '.join(context.intent.assumptions)}")

        if context.project_context:
            parts.append(f"\nExisting project context: {context.project_context.get('summary', 'N/A')}")

        return "\n".join(parts)

    def _build_summary(self, data: dict[str, Any]) -> str:
        """Build a human-readable summary of the requirements."""
        stories = data.get("user_stories", [])
        story_count = len(stories)
        titles = [s.get("title", "Untitled") for s in stories[:3]]
        suffix = f" (+{story_count - 3} more)" if story_count > 3 else ""
        return f"Generated {story_count} user stories: {', '.join(titles)}{suffix}"
