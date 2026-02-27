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
    keyword: str | None = Field(
        default=None,
        description="Search keyword, e.g. `maimai` or `广州 maimai`.",
    )
    province_code: str | None = Field(
        default=None,
        description="12-digit province code when available, e.g. `440000000000`.",
    )
    city_code: str | None = Field(
        default=None,
        description="12-digit city code when available, e.g. `440100000000`.",
    )
    county_code: str | None = Field(
        default=None,
        description="12-digit county code when available.",
    )
    province_name: str | None = Field(
        default=None,
        description="Province name when code is unavailable, e.g. `广东`.",
    )
    city_name: str | None = Field(
        default=None,
        description="City name when code is unavailable, e.g. `广州`.",
    )
    county_name: str | None = Field(
        default=None,
        description="County/district name when code is unavailable.",
    )
    has_arcades: bool | None = Field(
        default=None,
        description="Whether to require rows containing at least one title.",
    )
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=50)
    shop_id: int | None = None


class GeoResolveArgs(_StrictModel):
    province_code: str | None


class RoutePlanArgs(_StrictModel):
    provider: Literal["amap", "google", "none"]
    mode: Literal["walking", "driving"]
    origin: LocationArgs
    destination: LocationArgs


class SummaryArgs(_StrictModel):
    topic: Literal["search", "navigation"]
    keyword: str | None = None
    total: int | None = None
    shops: list[dict[str, Any]] | None = None
    shop_name: str | None = None
    route: dict[str, Any] | None = None


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
    "db_query_tool": (
        "Search arcade shops by keyword and region. "
        "Use *_code for 12-digit region codes, or *_name for natural-language region names. "
        "Can also fetch one shop by shop_id."
    ),
    "geo_resolve_tool": "Resolve map provider by province code.",
    "route_plan_tool": "Plan a route from origin to destination.",
    "summary_tool": "Generate concise text summary for search or navigation context.",
    "select_next_subagent": "Emit a compatibility hint for next subagent candidate; runtime policy decides final route.",
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
