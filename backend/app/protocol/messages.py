"""Protocol layer: request/response DTOs shared by API and orchestrator modules."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


IntentType = Literal["search_nearby", "navigate", "search"]
ChatRoleType = Literal["user", "assistant", "tool"]
ProviderType = Literal["amap", "google", "none"]


class Location(BaseModel):
    """Client-side location DTO."""

    lng: float = Field(..., description="Longitude in WGS84.")
    lat: float = Field(..., description="Latitude in WGS84.")


class ArcadeTitleDto(BaseModel):
    """Title machine item under a single shop."""

    id: int | None = None
    title_id: str | int | None = None
    title_name: str | None = None
    quantity: int | None = None
    version: str | None = None
    coin: str | int | float | None = None
    eacoin: str | int | float | None = None
    comment: str | None = None


class ArcadeShopSummaryDto(BaseModel):
    """Summary representation for listing/search APIs."""

    source: str
    source_id: int
    source_url: str
    name: str
    name_pinyin: str | None = None
    address: str | None = None
    transport: str | None = None
    province_code: str | None = None
    province_name: str | None = None
    city_code: str | None = None
    city_name: str | None = None
    county_code: str | None = None
    county_name: str | None = None
    status: int | str | None = None
    type: int | str | None = None
    pay_type: int | str | None = None
    locked: int | str | None = None
    ea_status: int | str | None = None
    price: str | int | float | None = None
    start_time: int | str | None = None
    end_time: int | str | None = None
    fav_count: int | None = None
    updated_at: str | None = None
    arcade_count: int = 0


class ArcadeShopDetailDto(ArcadeShopSummaryDto):
    """Detailed shop payload including titles/raw optional metadata."""

    comment: str | None = None
    url: str | None = None
    image_thumb: dict[str, Any] | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    arcades: list[ArcadeTitleDto] = Field(default_factory=list)
    collab: bool | None = None
    raw: dict[str, Any] | None = None


class PagedArcadeResponse(BaseModel):
    """Paginated list response contract."""

    items: list[ArcadeShopSummaryDto]
    page: int
    page_size: int
    total: int
    total_pages: int


class RegionItemDto(BaseModel):
    """Standardized region item for province/city/county endpoints."""

    code: str
    name: str


class RouteSummaryDto(BaseModel):
    """Route plan payload returned by navigation flow."""

    provider: ProviderType
    mode: str
    distance_m: int | None = None
    duration_s: int | None = None
    polyline: list[Location] = Field(default_factory=list)
    hint: str | None = None


class ChatRequest(BaseModel):
    """Chat entrypoint request used by the orchestrator."""

    session_id: str | None = None
    message: str = Field(..., min_length=1, max_length=2000)
    intent: IntentType | None = None
    shop_id: int | None = None
    location: Location | None = None
    keyword: str | None = None
    province_code: str | None = None
    city_code: str | None = None
    county_code: str | None = None
    page_size: int = Field(default=5, ge=1, le=50)


class ChatResponse(BaseModel):
    """Chat entrypoint response DTO."""

    session_id: str
    intent: IntentType
    reply: str
    shops: list[ArcadeShopSummaryDto] = Field(default_factory=list)
    route: RouteSummaryDto | None = None


class ChatHistoryTurnDto(BaseModel):
    """Persisted chat history turn for one session."""

    role: ChatRoleType
    content: str
    name: str | None = None
    call_id: str | None = None
    created_at: str


class ChatSessionSummaryDto(BaseModel):
    """Session summary card shown in sidebar/history list."""

    session_id: str
    title: str
    preview: str | None = None
    intent: IntentType
    turn_count: int
    created_at: str
    updated_at: str


class ChatSessionDetailDto(BaseModel):
    """Full session payload used to restore message history in UI."""

    session_id: str
    intent: IntentType
    active_subagent: str
    turn_count: int
    created_at: str
    updated_at: str
    turns: list[ChatHistoryTurnDto] = Field(default_factory=list)
