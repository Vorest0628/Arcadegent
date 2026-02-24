"""Builtin tool to select next subagent according to policy inputs."""

from __future__ import annotations


class SelectNextSubagentTool:
    """Map runtime signals to the next subagent."""

    def select_next_subagent(
        self,
        *,
        current_subagent: str,
        intent: str | None,
        tool_name: str | None,
        tool_status: str,
        has_route: bool,
        has_shops: bool,
    ) -> dict[str, str | bool | None]:
        normalized_intent = intent or "search"
        if current_subagent == "intent_router":
            if normalized_intent == "navigate":
                next_subagent = "navigation_agent"
            else:
                next_subagent = "search_agent"
        elif current_subagent == "navigation_agent":
            if tool_name == "route_plan_tool" and tool_status == "completed" and has_route:
                next_subagent = "summary_agent"
            else:
                next_subagent = "navigation_agent"
        elif current_subagent == "search_agent":
            if tool_name in {"db_query_tool", "summary_tool"} and tool_status == "completed":
                next_subagent = "summary_agent"
            elif has_shops:
                next_subagent = "summary_agent"
            else:
                next_subagent = "search_agent"
        else:
            next_subagent = "summary_agent"

        done = bool(next_subagent == "summary_agent" and tool_name == "summary_tool" and tool_status == "completed")
        return {
            "next_subagent": next_subagent,
            "intent": normalized_intent,
            "done": done,
        }

