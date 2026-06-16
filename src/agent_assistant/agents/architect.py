"""Architect Agent — architecture design stage."""

from __future__ import annotations

import json
from typing import Any

from agent_assistant.llm.client import ChatMessage
from agent_assistant.pipeline.agent import Agent, AgentRole
from agent_assistant.pipeline.artifact import Artifact
from agent_assistant.pipeline.context import AgentContext

ARCHITECT_SYSTEM_PROMPT = """\
You are a senior software architect. Given requirements and (optionally) existing \
project context, produce a technical architecture design.

Output ONLY valid JSON with this schema:

{
  "modules": [
    {
      "name": "module_name",
      "purpose": "What this module does",
      "responsibilities": ["List of responsibilities"]
    }
  ],
  "interfaces": [
    {
      "name": "InterfaceName",
      "type": "api | service | data | event",
      "description": "What this interface exposes",
      "methods": ["method signatures or descriptions"]
    }
  ],
  "tech_choices": [
    {"technology": "name", "reason": "why this was chosen"}
  ],
  "data_flow": "Description of how data flows through the system",
  "risks": ["Potential technical risks or challenges"]
}

Rules:
- Design modules that are cohesive (single responsibility) and loosely coupled.
- Define clear interfaces between modules.
- Prefer proven technologies unless the requirements demand something novel.
- Identify 2-3 key technical risks.
- If existing project context is provided, design to integrate with it.
"""


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)
    return text.strip()


class ArchitectAgent(Agent):
    """Architect agent that produces architecture designs from requirements."""

    def __init__(self) -> None:
        super().__init__(AgentRole.ARCHITECT)

    def execute(self, context: AgentContext) -> Artifact:
        pm_artifact = context.get_upstream_artifact("pm")
        if pm_artifact is None:
            raise ValueError("Architect requires PM artifact as input")

        user_prompt = self._build_prompt(context, pm_artifact)
        messages = [
            ChatMessage(role="system", content=ARCHITECT_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ]

        response = context.llm_client.chat(messages)
        raw_json = _extract_json(response.content)
        data = json.loads(raw_json)

        summary = self._build_summary(data)
        return Artifact(stage=self.role.value, summary=summary, structured_data=data)

    def _build_prompt(self, context: AgentContext, pm_artifact: Artifact) -> str:
        parts = [
            f"Feature: {context.intent.feature}",
            f"\nRequirements:\n{json.dumps(pm_artifact.structured_data, indent=2, ensure_ascii=False)}",
        ]
        if context.project_context:
            parts.append(f"\nExisting project:\n{json.dumps(context.project_context, indent=2, ensure_ascii=False)[:2000]}")
        return "\n".join(parts)

    def _build_summary(self, data: dict[str, Any]) -> str:
        modules = data.get("modules", [])
        names = [m.get("name", "?") for m in modules[:3]]
        suffix = f" (+{len(modules) - 3} more)" if len(modules) > 3 else ""
        return f"Architecture: {len(modules)} modules — {', '.join(names)}{suffix}"
