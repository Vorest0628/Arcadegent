"""Unit tests for context builder skill and memory injection."""

from __future__ import annotations

from pathlib import Path

from app.agent.context.context_builder import ContextBuilder
from app.agent.runtime.session_state import AgentSessionState, AgentTurn
from app.agent.subagents.subagent_builder import SubAgentProfile
from app.protocol.messages import ChatRequest


def test_context_builder_injects_skill_content_and_memory_snapshot(tmp_path: Path) -> None:
    prompt_root = tmp_path / "prompts"
    skill_root = tmp_path / "skills"
    prompt_root.mkdir()
    skill_root.mkdir()
    (prompt_root / "system_base.md").write_text("base prompt", encoding="utf-8")
    (prompt_root / "summary_agent.md").write_text("summary prompt", encoding="utf-8")
    (skill_root / "search_result_reading.md").write_text("search skill", encoding="utf-8")

    builder = ContextBuilder(
        prompt_root=prompt_root,
        skill_root=skill_root,
        history_turn_limit=6,
    )
    state = AgentSessionState(
        session_id="s1",
        active_subagent="summary_agent",
        turns=[
            AgentTurn(role="user", content="find maimai"),
            AgentTurn(
                role="tool",
                name="db_query_tool",
                call_id="call_1",
                content='{"total": 2}',
            ),
        ],
    )
    state.working_memory.update(
        {
            "keyword": "maimai",
            "total": 2,
            "last_db_query": {"sort_by": "title_quantity", "sort_title_name": "maimai"},
            "shops": [
                {
                    "source_id": 1,
                    "name": "Alpha",
                    "city_name": "Shanghai",
                    "arcades": [{"title_name": "maimai DX", "quantity": 4}],
                }
            ],
        }
    )

    context = builder.build(
        session_state=state,
        request=ChatRequest(message="find maimai"),
        subagent=SubAgentProfile(
            name="summary_agent",
            prompt_file="summary_agent.md",
            allowed_tools=[],
            skill_files=["search_result_reading.md"],
        ),
    )

    assert "base prompt" in context.instructions
    assert "summary prompt" in context.instructions
    assert "Skill reference: search_result_reading.md" in context.instructions
    assert "search skill" in context.instructions
    assert '"total": 2' in context.instructions
    assert '"shops_preview"' in context.instructions
    assert '"quantity": 4' in context.instructions
    assert context.messages[1]["role"] == "tool"
