"""In-memory session state for multi-turn ReAct execution."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Literal

TurnRole = Literal["user", "assistant", "tool"]


def _utc_now_iso() -> str:
    """Generate UTC ISO8601 timestamp used by chat session snapshots."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class AgentTurn:
    """One persisted turn item for model context reconstruction."""

    role: TurnRole
    content: str
    name: str | None = None
    call_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)


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
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)


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

    def snapshot(self, session_id: str) -> AgentSessionState | None:
        """Return deep-copied session state for API serialization."""
        with self._lock:
            state = self._states.get(session_id)
            if state is None:
                return None
            return deepcopy(state)

    def list_snapshots(self, *, limit: int = 50) -> list[AgentSessionState]:
        """Return recent session snapshots sorted by updated_at desc."""
        safe_limit = max(1, min(limit, 200))
        with self._lock:
            snapshots = [deepcopy(item) for item in self._states.values()]
        snapshots.sort(key=lambda item: item.updated_at, reverse=True)
        return snapshots[:safe_limit]

    def delete(self, session_id: str) -> bool:
        """Delete one session by id; return True when it existed."""
        with self._lock:
            existed = session_id in self._states
            if existed:
                del self._states[session_id]
            return existed
