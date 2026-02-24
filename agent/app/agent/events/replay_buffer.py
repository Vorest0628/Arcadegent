"""Event layer: bounded in-memory replay buffer for per-session SSE reconnect."""

from __future__ import annotations

from collections import deque
from threading import Lock

from app.agent.events.event_types import EventName, StreamEvent


class ReplayBuffer:
    """Keep recent events by session_id and support replay from last_event_id."""

    def __init__(self, max_events_per_session: int = 200) -> None:
        self._max_events_per_session = max(10, max_events_per_session)
        self._sessions: dict[str, deque[StreamEvent]] = {}
        self._seq = 0
        self._lock = Lock()

    def append(self, session_id: str, event_name: EventName, data: dict | None = None) -> StreamEvent:
        """Append a stream event and return it."""
        with self._lock:
            self._seq += 1
            event = StreamEvent(
                id=self._seq,
                session_id=session_id,
                event=event_name,
                data=data or {},
            )
            bucket = self._sessions.setdefault(session_id, deque(maxlen=self._max_events_per_session))
            bucket.append(event)
            return event

    def list_events(self, session_id: str, last_event_id: int | None = None) -> list[StreamEvent]:
        """List buffered events newer than last_event_id."""
        with self._lock:
            bucket = self._sessions.get(session_id)
            if not bucket:
                return []
            if last_event_id is None:
                return list(bucket)
            return [item for item in bucket if item.id > last_event_id]

