"""In-memory session state for multi-turn ReAct execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Literal

TurnRole = Literal["user", "assistant", "tool"]


@dataclass
class AgentTurn:
    """One persisted turn item for model context reconstruction."""

    role: TurnRole
    content: str
    name: str | None = None
    call_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentSessionState:
    """Session-level execution state and memory."""

    session_id: str
    turn_index: int = 0
    active_subagent: str = "intent_router"
    intent: str = "search"
    turns: list[AgentTurn] = field(default_factory=list)
    working_memory: dict[str, Any] = field(default_factory=dict)
    previous_response_id: str | None = None


class SessionStateStore:
    """Thread-safe in-memory state store keyed by session_id."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._states: dict[str, AgentSessionState] = {}

    def get_or_create(self, session_id: str) -> AgentSessionState:
        with self._lock:
            state = self._states.get(session_id)
            if state is None:
                state = AgentSessionState(session_id=session_id)
                self._states[session_id] = state
            return state

