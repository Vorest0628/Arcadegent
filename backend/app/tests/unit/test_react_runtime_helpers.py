"""Unit tests for ReactRuntime helper behaviors."""

from __future__ import annotations

from app.agent.runtime.react_runtime import _chunk_stream_text
from app.agent.runtime.session_state import AgentSessionState
from app.agent.runtime.tool_action_observer import ToolActionObserver


def _observer() -> ToolActionObserver:
    # Helper methods below do not depend on initialized collaborators.
    return object.__new__(ToolActionObserver)


def test_prepare_tool_arguments_hydrates_search_summary_from_memory() -> None:
    observer = _observer()
    state = AgentSessionState(session_id="s1")
    state.working_memory.update(
        {
            "total": 5,
            "shops": [{"name": "A"}, {"name": "B"}],
            "keyword": "shanghai huangpu",
        }
    )

    args, hydrated = observer._prepare_tool_arguments(
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
    observer = _observer()
    state = AgentSessionState(session_id="s2")
    state.working_memory.update(
        {
            "route": {"provider": "amap", "mode": "walking"},
            "shops": [{"name": "Foo Arcade"}],
        }
    )

    args, hydrated = observer._prepare_tool_arguments(
        state=state,
        tool_name="summary_tool",
        raw_arguments={"topic": "navigation"},
    )

    assert args["topic"] == "navigation"
    assert isinstance(args["route"], dict)
    assert args["shop_name"] == "Foo Arcade"
    assert hydrated == ["route", "shop_name"]


def test_prepare_tool_arguments_keeps_non_summary_tools_unchanged() -> None:
    observer = _observer()
    state = AgentSessionState(session_id="s3")

    args, hydrated = observer._prepare_tool_arguments(
        state=state,
        tool_name="db_query_tool",
        raw_arguments={"page": 1},
    )

    assert args == {"page": 1}
    assert hydrated == []


def test_prepare_tool_arguments_hydrates_sort_fields_from_last_db_query() -> None:
    observer = _observer()
    state = AgentSessionState(session_id="s4")
    state.working_memory.update(
        {
            "total": 8,
            "shops": [{"name": "A"}],
            "keyword": "maimai",
            "last_db_query": {
                "sort_by": "title_quantity",
                "sort_order": "desc",
                "sort_title_name": "maimai",
            },
        }
    )

    args, hydrated = observer._prepare_tool_arguments(
        state=state,
        tool_name="summary_tool",
        raw_arguments={"topic": "search"},
    )

    assert args["sort_by"] == "title_quantity"
    assert args["sort_order"] == "desc"
    assert args["sort_title_name"] == "maimai"
    assert "sort_by" in hydrated
    assert "sort_order" in hydrated
    assert "sort_title_name" in hydrated


def test_prepare_tool_arguments_overrides_default_sort_with_title_quantity_context() -> None:
    observer = _observer()
    state = AgentSessionState(session_id="s5")
    state.working_memory.update(
        {
            "total": 6,
            "shops": [{"name": "A"}],
            "last_db_query": {
                "sort_by": "title_quantity",
                "sort_order": "desc",
                "sort_title_name": "maimai",
            },
        }
    )

    args, hydrated = observer._prepare_tool_arguments(
        state=state,
        tool_name="summary_tool",
        raw_arguments={"topic": "search", "sort_by": "default"},
    )

    assert args["sort_by"] == "title_quantity"
    assert args["sort_order"] == "desc"
    assert args["sort_title_name"] == "maimai"
    assert "sort_by" in hydrated


def test_chunk_stream_text_keeps_order_and_sentence_boundary() -> None:
    text = "First sentence. Second sentence is a little longer and should be chunked!"

    chunks = _chunk_stream_text(text, max_chars=8)

    assert "".join(chunks) == text
    assert any(item.endswith(".") for item in chunks)
    assert any(item.endswith("!") for item in chunks)
