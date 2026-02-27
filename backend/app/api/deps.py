"""API layer: dependency helpers to access shared container from request state."""

from __future__ import annotations

from fastapi import Request

from app.core.container import AppContainer


def get_container(request: Request) -> AppContainer:
    return request.app.state.container  # type: ignore[return-value]

