"""Executor for the builtin deterministic summary tool."""

from __future__ import annotations

from typing import Any

from app.agent.tools.builtin.provider import BuiltinToolContext
from app.protocol.messages import RouteSummaryDto


def execute(context: BuiltinToolContext, args: dict[str, Any]) -> dict[str, str]:
    """Format either search or navigation context into a stable reply string."""
    tool = context.require("summary_tool")
    if args["topic"] == "navigation":
        route_payload = args.get("route") or {}
        route = RouteSummaryDto.model_validate(route_payload)
        reply = tool.summarize_navigation(
            shop_name=args.get("shop_name") or "target arcade",
            route=route,
        )
    else:
        reply = tool.summarize_search(
            keyword=args.get("keyword"),
            total=int(args.get("total") or 0),
            shops=args.get("shops") or [],
            sort_by=args.get("sort_by"),
            sort_order=args.get("sort_order"),
            sort_title_name=args.get("sort_title_name"),
        )
    return {"reply": reply}
