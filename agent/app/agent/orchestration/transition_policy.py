"""State transition policy for subagent switching."""

from __future__ import annotations

from typing import Any


class TransitionPolicy:
    """Determine next subagent from tool execution outcomes."""

    def next_subagent(
        self,
        *,
        current_subagent: str,
        tool_name: str,
        tool_status: str,
        tool_output: dict[str, Any],
        fallback_intent: str,
    ) -> str:
        if tool_name == "select_next_subagent":
            candidate = tool_output.get("next_subagent")
            if isinstance(candidate, str) and candidate:
                return candidate
            return "navigation_agent" if fallback_intent == "navigate" else "search_agent"

        if tool_status != "completed":
            return current_subagent

        if tool_name == "db_query_tool":
            if current_subagent == "navigation_agent":
                return "navigation_agent"
            return "summary_agent"
        if tool_name == "geo_resolve_tool":
            return "navigation_agent"
        if tool_name == "route_plan_tool":
            return "summary_agent"
        if tool_name == "summary_tool":
            return "summary_agent"
        return current_subagent

    def is_terminal_tool(self, *, tool_name: str, tool_status: str) -> bool:
        return tool_name == "summary_tool" and tool_status == "completed"

