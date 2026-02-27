"""Compatibility entrypoint: delegate chat execution to ReAct runtime."""

from __future__ import annotations

from app.agent.runtime.react_runtime import ReactRuntime
from app.protocol.messages import ChatRequest, ChatResponse


class Orchestrator:
    """Backward-compatible orchestrator facade."""

    def __init__(self, *, react_runtime: ReactRuntime) -> None:
        self._react_runtime = react_runtime

    def run_chat(self, request: ChatRequest) -> ChatResponse:
        return self._react_runtime.run_chat(request)
