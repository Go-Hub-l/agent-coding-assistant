"""LLM client — thin wrapper around OpenAI-compatible chat completions API."""

from dataclasses import dataclass

import httpx

from agent_assistant.config import Config


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ChatResponse:
    content: str
    model: str
    usage: dict


class LLMClient:
    """OpenAI-compatible chat completions client."""

    def __init__(self, config: Config, model: str | None = None):
        self._base_url = config.base_url.rstrip("/")
        self._api_key = config.api_key
        self._model = model or config.models.orchestrator

    def chat(self, messages: list[ChatMessage], temperature: float = 0.3) -> ChatResponse:
        """Send a chat completion request and return the response."""
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self._base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        return ChatResponse(
            content=choice["message"]["content"],
            model=data.get("model", self._model),
            usage=data.get("usage", {}),
        )
