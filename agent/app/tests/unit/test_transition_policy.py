"""Unit tests for centralized subagent transition policy."""

from __future__ import annotations

from app.agent.orchestration.transition_policy import TransitionPolicy


def test_select_candidate_is_only_hint_for_navigate_intent() -> None:
    policy = TransitionPolicy()

    next_subagent = policy.next_subagent(
        current_subagent="intent_router",
        tool_name="select_next_subagent",
        tool_status="completed",
        tool_output={"next_subagent": "search_agent"},
        fallback_intent="navigate",
        has_route=False,
        has_shops=False,
    )

    assert next_subagent == "navigation_agent"


def test_search_db_result_routes_to_summary_when_shops_exist() -> None:
    policy = TransitionPolicy()

    next_subagent = policy.next_subagent(
        current_subagent="search_agent",
        tool_name="db_query_tool",
        tool_status="completed",
        tool_output={},
        fallback_intent="search",
        has_route=False,
        has_shops=True,
    )

    assert next_subagent == "summary_agent"


def test_route_plan_without_route_keeps_navigation_stage() -> None:
    policy = TransitionPolicy()

    next_subagent = policy.next_subagent(
        current_subagent="navigation_agent",
        tool_name="route_plan_tool",
        tool_status="completed",
        tool_output={},
        fallback_intent="navigate",
        has_route=False,
        has_shops=False,
    )

    assert next_subagent == "navigation_agent"
