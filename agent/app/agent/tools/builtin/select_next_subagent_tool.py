"""Compatibility tool that emits next-subagent hint signals."""

from __future__ import annotations


class SelectNextSubagentTool:
    """Provide candidate routing hints; policy remains the source of truth."""

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
        normalized_intent = "navigate" if intent == "navigate" else "search"
        next_subagent = self._suggest_candidate(
            current_subagent=current_subagent,
            normalized_intent=normalized_intent,
            tool_name=tool_name,
            tool_status=tool_status,
            has_route=has_route,
            has_shops=has_shops,
        )
        done = bool(tool_name == "summary_tool" and tool_status == "completed")
        return {
            "next_subagent": next_subagent,
            "intent": normalized_intent,
            "done": done,
        }

    def _suggest_candidate(
        self,
        *,
        current_subagent: str,
        normalized_intent: str,
        tool_name: str | None,
        tool_status: str,
        has_route: bool,
        has_shops: bool,
    ) -> str:
        if current_subagent == "intent_router":
            return "navigation_agent" if normalized_intent == "navigate" else "search_agent"

        if tool_status == "completed":
            if tool_name == "route_plan_tool" and has_route:
                return "summary_agent"
            if tool_name == "db_query_tool" and (has_shops or current_subagent == "search_agent"):
                return "summary_agent"
            if has_route or has_shops:
                return "summary_agent"

        if current_subagent in {"search_agent", "navigation_agent", "summary_agent"}:
            return current_subagent
        return "navigation_agent" if normalized_intent == "navigate" else "search_agent"
