"""LLM config resolver for ReAct runtime and provider adapter."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings


@dataclass(frozen=True)
class LLMConfig:
    """Normalized LLM runtime configuration."""

    api_key: str
    base_url: str
    model: str
    timeout_seconds: float
    temperature: float
    max_tokens: int
    tool_choice: str = "auto"
    parallel_tool_calls: bool = False

    @property
    def enabled(self) -> bool:
        return bool(self.api_key.strip())


def resolve_llm_config(settings: Settings) -> LLMConfig:
    """Build LLM config from app settings with defensive bounds."""
    return LLMConfig(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=max(1.0, float(settings.llm_timeout_seconds)),
        temperature=max(0.0, float(settings.llm_temperature)),
        max_tokens=max(32, int(settings.llm_max_tokens)),
        tool_choice="auto",
        parallel_tool_calls=False,
    )

