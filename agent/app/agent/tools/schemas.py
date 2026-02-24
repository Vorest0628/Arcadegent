"""Tool argument schemas and function definition builders."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LocationArgs(_StrictModel):
    lng: float
    lat: float


class DBQueryArgs(_StrictModel):
    keyword: str | None
    province_code: str | None
    city_code: str | None
    county_code: str | None
    has_arcades: bool | None
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=50)
    shop_id: int | None


class GeoResolveArgs(_StrictModel):
    province_code: str | None


class RoutePlanArgs(_StrictModel):
    provider: Literal["amap", "google", "none"]
    mode: Literal["walking", "driving"]
    origin: LocationArgs
    destination: LocationArgs


class SummaryArgs(_StrictModel):
    topic: Literal["search", "navigation"]
    keyword: str | None
    total: int | None
    shops: list[dict[str, Any]] | None
    shop_name: str | None
    route: dict[str, Any] | None


class SelectNextSubagentArgs(_StrictModel):
    current_subagent: str
    intent: str | None
    tool_name: str | None
    tool_status: Literal["completed", "failed"]
    has_route: bool
    has_shops: bool


TOOL_ARG_MODELS: dict[str, type[_StrictModel]] = {
    "db_query_tool": DBQueryArgs,
    "geo_resolve_tool": GeoResolveArgs,
    "route_plan_tool": RoutePlanArgs,
    "summary_tool": SummaryArgs,
    "select_next_subagent": SelectNextSubagentArgs,
}

TOOL_DESCRIPTIONS: dict[str, str] = {
    "db_query_tool": "Search arcade shops with filters, or fetch one shop by shop_id.",
    "geo_resolve_tool": "Resolve map provider by province code.",
    "route_plan_tool": "Plan a route from origin to destination.",
    "summary_tool": "Generate concise text summary for search or navigation context.",
    "select_next_subagent": "Select next subagent stage according to intent and tool outcomes.",
}


def build_tool_definitions(tool_names: list[str], *, strict: bool) -> list[dict[str, Any]]:
    """Build OpenAI-compatible function tool definitions."""
    definitions: list[dict[str, Any]] = []
    for name in tool_names:
        model = TOOL_ARG_MODELS.get(name)
        if model is None:
            continue
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": TOOL_DESCRIPTIONS.get(name, name),
                    "parameters": model.model_json_schema(),
                    "strict": strict,
                },
            }
        )
    return definitions

