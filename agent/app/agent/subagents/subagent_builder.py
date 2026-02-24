"""Subagent profile registry used by ReAct runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.protocol.messages import IntentType

SubAgentName = Literal["intent_router", "search_agent", "navigation_agent", "summary_agent"]


@dataclass(frozen=True)
class SubAgentProfile:
    """Execution profile for one subagent."""

    name: SubAgentName
    prompt_file: str
    allowed_tools: list[str]


class SubAgentBuilder:
    """Resolve subagent profiles by name and routing hints."""

    def __init__(self) -> None:
        self._profiles: dict[str, SubAgentProfile] = {
            "intent_router": SubAgentProfile(
                name="intent_router",
                prompt_file="intent_router.md",
                allowed_tools=["select_next_subagent"],
            ),
            "search_agent": SubAgentProfile(
                name="search_agent",
                prompt_file="search_agent.md",
                allowed_tools=["db_query_tool", "summary_tool", "select_next_subagent"],
            ),
            "navigation_agent": SubAgentProfile(
                name="navigation_agent",
                prompt_file="navigation_agent.md",
                allowed_tools=[
                    "db_query_tool",
                    "geo_resolve_tool",
                    "route_plan_tool",
                    "summary_tool",
                    "select_next_subagent",
                ],
            ),
            "summary_agent": SubAgentProfile(
                name="summary_agent",
                prompt_file="summary_agent.md",
                allowed_tools=["summary_tool"],
            ),
        }

    def get(self, name: str) -> SubAgentProfile:
        return self._profiles.get(name, self._profiles["intent_router"])

    def resolve_initial(self, intent: IntentType | None) -> SubAgentName:
        if intent == "navigate":
            return "navigation_agent"
        return "search_agent"

