"""Tester Agent — test generation and execution stage."""

from __future__ import annotations

import json
from typing import Any

from agent_assistant.llm.client import ChatMessage
from agent_assistant.pipeline.agent import Agent, AgentRole
from agent_assistant.pipeline.artifact import Artifact
from agent_assistant.pipeline.context import AgentContext

TESTER_SYSTEM_PROMPT = """\
You are a senior QA engineer and test architect. Given the implemented code \
and its architecture design, generate comprehensive test suites and assess \
their quality.

Output ONLY valid JSON with this schema (no markdown fences, no commentary):

{
  "test_files": [
    {
      "path": "tests/test_module.py",
      "content": "full test file content as a string",
      "description": "What this test file covers"
    }
  ],
  "results": {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "failures": []
  },
  "verdict": "passed | failed",
  "summary": "Brief summary of test results"
}

Verdict rules:
- "passed": All tests pass. The implementation meets quality standards.
- "failed": One or more tests fail. Include failure details in the results.

Rules:
- Write tests that verify behavior, not implementation details.
- Cover happy paths, edge cases, and error handling.
- Use the project's testing framework (pytest for Python, Jest for JS, etc.).
- Each test file should be complete and runnable.
- Include meaningful test names that describe the behavior being tested.
- If previous test failures are provided, fix the tests or the underlying \
  issue and regenerate all tests.
- The results should reflect your assessment of whether the tests would pass.
"""


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)
    return text.strip()


class TesterAgent(Agent):
    """Tester agent that generates and assesses test suites."""

    def __init__(self) -> None:
        super().__init__(AgentRole.TESTER)

    def execute(self, context: AgentContext) -> Artifact:
        coder_artifact = context.get_upstream_artifact("coder")
        if coder_artifact is None:
            raise ValueError("Tester requires Coder artifact as input")

        arch_artifact = context.get_upstream_artifact("architect")
        pm_artifact = context.get_upstream_artifact("pm")

        user_prompt = self._build_prompt(context, coder_artifact, arch_artifact, pm_artifact)

        messages = [
            ChatMessage(role="system", content=TESTER_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ]

        if context.feedback:
            messages.append(ChatMessage(
                role="user",
                content=f"Previous test failures to address:\n{context.feedback}",
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
            f"\nImplemented code:\n{json.dumps(coder.structured_data, indent=2, ensure_ascii=False)}",
        ]
        if arch:
            parts.append(f"\nArchitecture (for context):\n{json.dumps(arch.structured_data, indent=2, ensure_ascii=False)[:2000]}")
        if pm:
            parts.append(f"\nRequirements:\n{json.dumps(pm.structured_data, indent=2, ensure_ascii=False)[:2000]}")
        return "\n".join(parts)

    def _build_summary(self, data: dict[str, Any]) -> str:
        verdict = data.get("verdict", "unknown")
        results = data.get("results", {})
        total = results.get("total", 0)
        passed = results.get("passed", 0)
        failed = results.get("failed", 0)
        if failed > 0:
            return f"Tests {verdict}: {passed}/{total} passed, {failed} failed"
        return f"Tests {verdict}: {total}/{total} passed"
