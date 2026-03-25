"""Executor for the builtin provider selection tool."""

from __future__ import annotations

from app.agent.tools.builtin.provider import BuiltinToolContext


def execute(context: BuiltinToolContext, args: dict[str, object]) -> dict[str, str]:
    """Resolve the provider for one province code."""
    tool = context.require("geo_resolve_tool")
    provider = tool.resolve_provider(args.get("province_code"))
    return {"provider": provider}
