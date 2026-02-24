"""Stream API layer: SSE endpoint with replay support and heartbeat."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.deps import get_container
from app.core.container import AppContainer

router = APIRouter(tags=["stream"])


def _format_sse(*, event: str, data: dict, event_id: int) -> str:
    body = json.dumps(data, ensure_ascii=False)
    return f"id: {event_id}\nevent: {event}\ndata: {body}\n\n"


@router.get("/api/stream/{session_id}")
async def stream(
    session_id: str,
    last_event_id: int | None = Query(default=None),
    container: AppContainer = Depends(get_container),
) -> StreamingResponse:
    async def iterator() -> AsyncIterator[str]:
        cursor = last_event_id
        waited = 0
        while waited < container.settings.sse_max_wait_seconds:
            events = container.replay_buffer.list_events(session_id, cursor)
            if events:
                for evt in events:
                    cursor = evt.id
                    yield _format_sse(
                        event=evt.event,
                        data=evt.model_dump(mode="json"),
                        event_id=evt.id,
                    )
            else:
                yield ": keep-alive\n\n"
            waited += 1
            await asyncio.sleep(container.settings.sse_keepalive_seconds)

    return StreamingResponse(iterator(), media_type="text/event-stream")

