"""LLM config resolver for ReAct runtime and provider adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

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


def _load_profile(profile_file: Path, profile_name: str) -> dict[str, Any]:
    if not profile_file.exists():
        return {}
    try:
        raw = yaml.safe_load(profile_file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(raw, dict):
        return {}
    profiles = raw.get("profiles")
    if not isinstance(profiles, dict):
        return {}
    payload = profiles.get(profile_name)
    if not isinstance(payload, dict):
        payload = profiles.get("default")
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("llm")
    if isinstance(nested, dict):
        merged = dict(payload)
        merged.update(nested)
        return merged
    return payload


def _pick_str(payload: dict[str, Any], key: str, fallback: str) -> str:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _pick_float(payload: dict[str, Any], key: str, fallback: float) -> float:
    value = payload.get(key)
    if isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return fallback
    return fallback


def _pick_int(payload: dict[str, Any], key: str, fallback: int) -> int:
    value = payload.get(key)
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return fallback
    return fallback


def _pick_bool(payload: dict[str, Any], key: str, fallback: bool) -> bool:
    value = payload.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return fallback


def resolve_llm_config(settings: Settings) -> LLMConfig:
    """Build LLM config from app settings with defensive bounds."""
    profile = _load_profile(
        settings.agent_provider_profiles_file,
        settings.agent_provider_profile,
    )
    enabled = _pick_bool(profile, "enabled", True)
    return LLMConfig(
        api_key=settings.llm_api_key if enabled else "",
        base_url=_pick_str(profile, "base_url", settings.llm_base_url),
        model=_pick_str(profile, "model", settings.llm_model),
        timeout_seconds=max(
            1.0,
            _pick_float(profile, "timeout_seconds", float(settings.llm_timeout_seconds)),
        ),
        temperature=max(
            0.0,
            _pick_float(profile, "temperature", float(settings.llm_temperature)),
        ),
        max_tokens=max(32, _pick_int(profile, "max_tokens", int(settings.llm_max_tokens))),
        tool_choice=_pick_str(profile, "tool_choice", "auto"),
        parallel_tool_calls=_pick_bool(profile, "parallel_tool_calls", False),
    )
