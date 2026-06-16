"""Project summarizer — LLM refinement of structural scan data."""

from __future__ import annotations

import json
from typing import Any

from agent_assistant.llm.client import ChatMessage, LLMClient
from agent_assistant.project_context.scanner import ScanResult

SUMMARIZER_SYSTEM_PROMPT = """\
You are a senior software architect. Given structural scan data of a codebase, \
produce a concise semantic summary that helps other agents understand the project.

Output ONLY valid JSON:

{
  "project_type": "e.g. web app, CLI tool, library, API service",
  "tech_stack": ["list of key technologies and frameworks"],
  "architecture": "Brief description of the high-level architecture",
  "key_modules": [
    {"name": "module name", "purpose": "what it does"}
  ],
  "patterns": ["Notable patterns: e.g. MVC, event-driven, monorepo"]
}

Rules:
- Focus on WHAT the project does, not just what files exist.
- Identify the primary purpose and domain of the project.
- Note any unusual or noteworthy architectural decisions.
- Keep the summary under 300 words total.
"""


class ProjectSummarizer:
    """Uses an LLM to refine structural scan data into a semantic summary."""

    def __init__(self, llm: LLMClient):
        self._llm = llm

    def summarize(self, scan_result: ScanResult) -> dict[str, Any]:
        """Produce a semantic summary from scan data.

        Returns a dict with both the raw scan data and the LLM-generated summary.
        """
        user_prompt = self._build_prompt(scan_result)

        messages = [
            ChatMessage(role="system", content=SUMMARIZER_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ]

        response = self._llm.chat(messages)
        summary = self._extract_json(response.content)

        return {
            "summary": summary,
            "scan_data": scan_result.to_dict(),
        }

    def _build_prompt(self, scan: ScanResult) -> str:
        """Build a concise prompt from scan data."""
        parts = [
            f"Project directory: {scan.root_dir}",
            "",
            "File tree (first 50 entries):",
        ]
        parts.extend(f"  {f}" for f in scan.file_tree[:50])

        if scan.dependencies:
            parts.append("")
            parts.append("Dependencies:")
            for lang, deps in scan.dependencies.items():
                parts.append(f"  {lang}: {', '.join(deps[:20])}")

        if scan.files:
            parts.append("")
            parts.append(f"Source files ({len(scan.files)} scanned):")
            for f in scan.files[:30]:
                symbols = []
                if f.classes:
                    symbols.append(f"classes: {', '.join(f.classes[:5])}")
                if f.functions:
                    symbols.append(f"functions: {', '.join(f.functions[:5])}")
                sym_str = f" ({'; '.join(symbols)})" if symbols else ""
                parts.append(f"  {f.path}{sym_str}")

        if scan.entry_points:
            parts.append("")
            parts.append(f"Entry points: {', '.join(scan.entry_points)}")

        return "\n".join(parts)

    def _extract_json(self, text: str) -> dict[str, Any]:
        """Extract and parse JSON from LLM response."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            text = "\n".join(lines)
        return json.loads(text.strip())
