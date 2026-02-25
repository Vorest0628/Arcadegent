"""Context assembly for ReAct runtime turns."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.agent.runtime.session_state import AgentSessionState, AgentTurn
from app.agent.subagents.subagent_builder import SubAgentProfile
from app.protocol.messages import ChatRequest


@dataclass(frozen=True)
class BuiltContext:
    """Prepared prompt payload for provider adapter."""

    instructions: str
    messages: list[dict[str, Any]]


class ContextBuilder:
    """Build model instructions and messages from session history."""

    def __init__(self, *, prompt_root: Path, history_turn_limit: int) -> None:
        self._prompt_root = prompt_root
        self._history_turn_limit = max(4, history_turn_limit)
        self._prompt_cache: dict[str, str] = {}

    def build(
        self,
        *,
        session_state: AgentSessionState,
        request: ChatRequest,
        subagent: SubAgentProfile,
    ) -> BuiltContext:
        base_prompt = self._load_prompt("system_base.md")
        subagent_prompt = self._load_prompt(subagent.prompt_file)
        runtime_hint = {
            "session_id": session_state.session_id,
            "turn_index": session_state.turn_index,
            "active_subagent": session_state.active_subagent,
            "intent": session_state.intent,
            "request": request.model_dump(mode="json"),
            "memory_summary": {
                "has_shops": bool(session_state.working_memory.get("shops")),
                "has_route": bool(session_state.working_memory.get("route")),
            },
        }
        instructions = "\n\n".join(
            (
                base_prompt.strip(),
                subagent_prompt.strip(),
                "Runtime state (JSON):",
                json.dumps(runtime_hint, ensure_ascii=False),
            )
        )
        messages = [self._to_model_message(turn) for turn in self._tail_turns(session_state.turns)]
        return BuiltContext(instructions=instructions, messages=messages)

    """返回最近的历史对话，限制在history_turn_limit之内"""
    def _tail_turns(self, turns: list[AgentTurn]) -> list[AgentTurn]:
        if len(turns) <= self._history_turn_limit:
            return turns
        return turns[-self._history_turn_limit :]

    def _to_model_message(self, turn: AgentTurn) -> dict[str, Any]:
        if turn.role == "tool":
            payload: dict[str, Any] = {
                "role": "tool",
                "content": turn.content,
            }
            if turn.name:
                payload["name"] = turn.name
            if turn.call_id:
                payload["tool_call_id"] = turn.call_id
            return payload
        return {"role": turn.role, "content": turn.content}

    def _load_prompt(self, filename: str) -> str:
        if filename in self._prompt_cache:
            return self._prompt_cache[filename]
        path = self._prompt_root / filename
        if not path.exists():
            content = ""
        else:
            content = path.read_text(encoding="utf-8")
        self._prompt_cache[filename] = content
        return content

