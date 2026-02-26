"""Unit tests for ReactRuntime helper behaviors."""

from __future__ import annotations

from app.agent.runtime.react_runtime import ReactRuntime
from app.agent.runtime.session_state import AgentSessionState


def _runtime() -> ReactRuntime:
    # Helper methods below do not depend on initialized collaborators.
    return object.__new__(ReactRuntime)


def test_prepare_tool_arguments_hydrates_search_summary_from_memory() -> None:
    runtime = _runtime()
    state = AgentSessionState(session_id="s1")
    state.working_memory.update(
        {
            "total": 5,
            "shops": [{"name": "A"}, {"name": "B"}],
            "keyword": "shanghai huangpu",
        }
    )

    args, hydrated = runtime._prepare_tool_arguments(
        state=state,
        tool_name="summary_tool",
        raw_arguments={"topic": "search"},
    )

    assert args["topic"] == "search"
    assert args["total"] == 5
    assert isinstance(args["shops"], list)
    assert args["keyword"] == "shanghai huangpu"
    assert hydrated == ["total", "shops", "keyword"]


def test_prepare_tool_arguments_hydrates_navigation_summary_from_memory() -> None:
    runtime = _runtime()
    state = AgentSessionState(session_id="s2")
    state.working_memory.update(
        {
            "route": {"provider": "amap", "mode": "walking"},
            "shops": [{"name": "Foo Arcade"}],
        }
    )

    args, hydrated = runtime._prepare_tool_arguments(
        state=state,
        tool_name="summary_tool",
        raw_arguments={"topic": "navigation"},
    )

    assert args["topic"] == "navigation"
    assert isinstance(args["route"], dict)
    assert args["shop_name"] == "Foo Arcade"
    assert hydrated == ["route", "shop_name"]


def test_prepare_tool_arguments_keeps_non_summary_tools_unchanged() -> None:
    runtime = _runtime()
    state = AgentSessionState(session_id="s3")

    args, hydrated = runtime._prepare_tool_arguments(
        state=state,
        tool_name="db_query_tool",
        raw_arguments={"page": 1},
    )

    assert args == {"page": 1}
    assert hydrated == []
