"""Coder Agent — coding implementation stage."""

from __future__ import annotations

import json
from typing import Any

from agent_assistant.llm.client import ChatMessage
from agent_assistant.pipeline.agent import Agent, AgentRole
from agent_assistant.pipeline.artifact import Artifact
from agent_assistant.pipeline.context import AgentContext

CODER_SYSTEM_PROMPT = """\
You are a senior software engineer. Given an architecture design and requirements, \
produce the actual code implementation.

Output ONLY valid JSON with this schema:

{
  "files": [
    {
      "path": "relative/path/to/file.py",
      "content": "full file content as a string",
      "description": "What this file does"
    }
  ],
  "implementation_notes": "Any notes about the implementation decisions made"
}

Rules:
- Write clean, well-structured code that follows the architecture design.
- Include appropriate imports, type hints, and docstrings.
- Create all necessary files — don't leave placeholder comments.
- Use the technologies specified in the architecture design.
- Follow the project's existing code style if context is provided.
- Each file should be complete and runnable.
"""


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)
    return text.strip()


class CoderAgent(Agent):
    """Coder agent that produces code files from architecture designs."""

    def __init__(self) -> None:
        super().__init__(AgentRole.CODER)

    def execute(self, context: AgentContext) -> Artifact:
        architect_artifact = context.get_upstream_artifact("architect")
        if architect_artifact is None:
            raise ValueError("Coder requires Architect artifact as input")

        pm_artifact = context.get_upstream_artifact("pm")
        user_prompt = self._build_prompt(context, architect_artifact, pm_artifact)

        messages = [
            ChatMessage(role="system", content=CODER_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ]

        # Include feedback if this is a retry from reviewer/tester
        if context.feedback:
            messages.append(ChatMessage(
                role="user",
                content=f"Previous attempt had issues. Please fix:\n{context.feedback}",
            ))

        response = context.llm_client.chat(messages)
        raw_json = _extract_json(response.content)
        data = json.loads(raw_json)

        summary = self._build_summary(data)
        return Artifact(stage=self.role.value, summary=summary, structured_data=data)

    def _build_prompt(self, context: AgentContext, arch: Artifact, pm: Artifact | None) -> str:
        parts = [
            f"Feature: {context.intent.feature}",
            f"\nArchitecture:\n{json.dumps(arch.structured_data, indent=2, ensure_ascii=False)}",
        ]
        if pm:
            parts.append(f"\nRequirements:\n{json.dumps(pm.structured_data, indent=2, ensure_ascii=False)[:2000]}")
        if context.project_context:
            parts.append(f"\nExisting project:\n{json.dumps(context.project_context, indent=2, ensure_ascii=False)[:2000]}")
        return "\n".join(parts)

    def _build_summary(self, data: dict[str, Any]) -> str:
        files = data.get("files", [])
        paths = [f.get("path", "?") for f in files[:3]]
        suffix = f" (+{len(files) - 3} more)" if len(files) > 3 else ""
        return f"Generated {len(files)} files: {', '.join(paths)}{suffix}"
