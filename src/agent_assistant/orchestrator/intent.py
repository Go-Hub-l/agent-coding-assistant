"""Intent specification — parse natural-language requests into structured intent documents."""

import json
from dataclasses import asdict, dataclass, field

from agent_assistant.llm.client import ChatMessage, LLMClient

INTENT_SYSTEM_PROMPT = """\
You are a senior product manager. Your job is to parse a developer's natural-language \
request and produce a structured intent document.

Output ONLY valid JSON with this exact schema (no markdown fences, no commentary):

{
  "feature": "One-sentence description of the feature to build",
  "constraints": ["List of technical or business constraints"],
  "target_modules": ["List of modules or areas of the codebase affected"],
  "assumptions": ["List of assumptions you are making about the request"]
}

Rules:
- Keep each field concise but complete.
- If the request is vague, make reasonable assumptions and list them.
- constraints should include language/framework preferences if mentioned.
- target_modules should name logical areas (e.g. "auth", "api", "database"), not file paths.
"""

INTENT_CORRECTION_PROMPT = """\
The developer has provided corrections to the intent document:

{corrections}

Original intent:
{original_intent}

Please produce an updated intent document following the same JSON schema. \
Output ONLY valid JSON.
"""


@dataclass
class IntentDocument:
    """Structured representation of the user's development intent."""

    feature: str
    constraints: list[str] = field(default_factory=list)
    target_modules: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "IntentDocument":
        """Parse a JSON string into an IntentDocument."""
        data = json.loads(raw)
        return cls(
            feature=data["feature"],
            constraints=data.get("constraints", []),
            target_modules=data.get("target_modules", []),
            assumptions=data.get("assumptions", []),
        )

    def format_for_display(self) -> str:
        """Format the intent document for terminal display."""
        lines = [f"  Feature: {self.feature}", ""]

        if self.constraints:
            lines.append("  Constraints:")
            for c in self.constraints:
                lines.append(f"    - {c}")
            lines.append("")

        if self.target_modules:
            lines.append("  Target Modules:")
            for m in self.target_modules:
                lines.append(f"    - {m}")
            lines.append("")

        if self.assumptions:
            lines.append("  Assumptions:")
            for a in self.assumptions:
                lines.append(f"    - {a}")

        return "\n".join(lines)


def _extract_json(text: str) -> str:
    """Extract JSON from LLM response that may contain markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (``` fences)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return text.strip()


def parse_intent(llm: LLMClient, request: str) -> IntentDocument:
    """Parse a natural-language request into a structured intent document."""
    messages = [
        ChatMessage(role="system", content=INTENT_SYSTEM_PROMPT),
        ChatMessage(role="user", content=request),
    ]
    response = llm.chat(messages)
    raw_json = _extract_json(response.content)
    return IntentDocument.from_json(raw_json)


def correct_intent(llm: LLMClient, original: IntentDocument, corrections: str) -> IntentDocument:
    """Apply user corrections to an existing intent document."""
    prompt = INTENT_CORRECTION_PROMPT.format(
        corrections=corrections,
        original_intent=original.to_json(),
    )
    messages = [
        ChatMessage(role="system", content=INTENT_SYSTEM_PROMPT),
        ChatMessage(role="user", content=prompt),
    ]
    response = llm.chat(messages)
    raw_json = _extract_json(response.content)
    return IntentDocument.from_json(raw_json)
