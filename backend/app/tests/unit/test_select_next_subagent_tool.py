"""Unit tests for compatibility-mode select_next_subagent tool."""

from __future__ import annotations

from app.agent.tools.builtin.select_next_subagent_tool import SelectNextSubagentTool


def test_select_next_subagent_tool_suggests_navigation_from_router() -> None:
    tool = SelectNextSubagentTool()

    result = tool.select_next_subagent(
        current_subagent="intent_router",
        intent="navigate",
        tool_name=None,
        tool_status="completed",
        has_route=False,
        has_shops=False,
    )

    assert result["next_subagent"] == "navigation_agent"
    assert result["intent"] == "navigate"
    assert result["done"] is False


def test_select_next_subagent_tool_suggests_summary_when_data_ready() -> None:
    tool = SelectNextSubagentTool()

    result = tool.select_next_subagent(
        current_subagent="search_agent",
        intent="search",
        tool_name="db_query_tool",
        tool_status="completed",
        has_route=False,
        has_shops=True,
    )

    assert result["next_subagent"] == "summary_agent"
    assert result["done"] is False


def test_select_next_subagent_tool_done_only_on_summary_completion() -> None:
    tool = SelectNextSubagentTool()

    result = tool.select_next_subagent(
        current_subagent="summary_agent",
        intent="search",
        tool_name="summary_tool",
        tool_status="completed",
        has_route=False,
        has_shops=True,
    )

    assert result["next_subagent"] == "summary_agent"
    assert result["done"] is True
