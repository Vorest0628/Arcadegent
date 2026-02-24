"""LLM infra: OpenAI-compatible chat.completions client via standard HTTP payload."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import error, request


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    """Runtime config for OpenAI-compatible API endpoints."""

    api_key: str
    base_url: str
    model: str
    timeout_seconds: float
    temperature: float
    max_tokens: int


class OpenAICompatibleClient:
    """Minimal sync client for `/v1/chat/completions` compatible providers."""

    def __init__(self, config: OpenAICompatibleConfig) -> None:
        self._config = config

    @property
    def enabled(self) -> bool:
        return bool(self._config.api_key.strip())

    def chat_completion(self, *, system_prompt: str, user_prompt: str) -> str | None:
        if not self.enabled:
            return None

        endpoint = self._config.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }

        req = request.Request(endpoint, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self._config.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except (error.URLError, error.HTTPError, TimeoutError):
            return None

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return None

        choices = decoded.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict):
            return None
        content = message.get("content")
        if isinstance(content, str):
            text = content.strip()
            return text if text else None
        return None

