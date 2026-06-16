"""Reviewer Agent — code review stage with quality assessment."""

from __future__ import annotations

import json
from typing import Any

from agent_assistant.llm.client import ChatMessage
from agent_assistant.pipeline.agent import Agent, AgentRole
from agent_assistant.pipeline.artifact import Artifact
from agent_assistant.pipeline.context import AgentContext

REVIEWER_SYSTEM_PROMPT = """\
You are a senior code reviewer with deep expertise in software quality, \
security, and maintainability. Your job is to review code produced by \
the Coder agent and assess its quality against the architecture design \
and requirements.

Output ONLY valid JSON with this schema (no markdown fences, no commentary):

{
  "issues": [
    {
      "severity": "critical | major | minor",
      "location": "file_path:line_number or file_path",
      "description": "What the problem is",
      "suggestion": "How to fix it"
    }
  ],
  "verdict": "approved | changes_requested | fundamental_issue",
  "summary": "Brief summary of the review"
}

Verdict rules:
- "approved": No critical or major issues. Code is ready to proceed.
- "changes_requested": There are critical or major issues that need fixing, \
  but the overall approach is sound. The Coder can fix these and resubmit.
- "fundamental_issue": The code has a fundamental problem that cannot be \
  fixed by the Coder alone. The architecture or requirements may need to \
  be revisited. This triggers a global rollback recommendation.

Severity guidelines:
- "critical": Security vulnerabilities, data loss risks, broken core functionality
- "major": Significant bugs, missing error handling, architecture violations
- "minor": Style issues, missing type hints, small improvements

Rules:
- Be thorough but constructive — every issue must include an actionable suggestion.
- Focus on correctness, security, and adherence to the architecture design.
- Minor style issues should not block approval unless pervasive.
- If the code is well-written and follows the design, approve it.
"""


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)
    return text.strip()


class ReviewerAgent(Agent):
    """Reviewer agent that assesses code quality and provides feedback."""

    def __init__(self) -> None:
        super().__init__(AgentRole.REVIEWER)

    def execute(self, context: AgentContext) -> Artifact:
        coder_artifact = context.get_upstream_artifact("coder")
        if coder_artifact is None:
            raise ValueError("Reviewer requires Coder artifact as input")

        arch_artifact = context.get_upstream_artifact("architect")
        pm_artifact = context.get_upstream_artifact("pm")

        user_prompt = self._build_prompt(context, coder_artifact, arch_artifact, pm_artifact)

        messages = [
            ChatMessage(role="system", content=REVIEWER_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ]

        if context.feedback:
            messages.append(ChatMessage(
                role="user",
                content=f"Previous review context: {context.feedback}",
            ))

        response = context.llm_client.chat(messages)
        raw_json = _extract_json(response.content)
        data = json.loads(raw_json)

        summary = self._build_summary(data)
        return Artifact(stage=self.role.value, summary=summary, structured_data=data)

    def _build_prompt(
        self,
        context: AgentContext,
        coder: Artifact,
        arch: Artifact | None,
        pm: Artifact | None,
    ) -> str:
        parts = [
            f"Feature: {context.intent.feature}",
            f"\nCode to review:\n{json.dumps(coder.structured_data, indent=2, ensure_ascii=False)}",
        ]
        if arch:
            parts.append(f"\nArchitecture (for reference):\n{json.dumps(arch.structured_data, indent=2, ensure_ascii=False)[:2000]}")
        if pm:
            parts.append(f"\nRequirements (for reference):\n{json.dumps(pm.structured_data, indent=2, ensure_ascii=False)[:2000]}")
        return "\n".join(parts)

    def _build_summary(self, data: dict[str, Any]) -> str:
        verdict = data.get("verdict", "unknown")
        issues = data.get("issues", [])
        if not issues:
            return f"Review: {verdict} — no issues found"
        severities = {}
        for issue in issues:
            sev = issue.get("severity", "unknown")
            severities[sev] = severities.get(sev, 0) + 1
        breakdown = ", ".join(f"{v} {k}" for k, v in severities.items())
        return f"Review: {verdict} — {len(issues)} issues ({breakdown})"
