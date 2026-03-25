"""Executor for the compatibility next-subagent hint tool."""

from __future__ import annotations

from typing import Any

from app.agent.tools.builtin.provider import BuiltinToolContext


def execute(context: BuiltinToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Delegate next-subagent hint generation to the builtin service object."""
    tool = context.require("select_next_subagent_tool")
    return tool.select_next_subagent(
        current_subagent=args["current_subagent"],
        intent=args.get("intent"),
        tool_name=args.get("tool_name"),
        tool_status=args["tool_status"],
        has_route=bool(args["has_route"]),
        has_shops=bool(args["has_shops"]),
    )
