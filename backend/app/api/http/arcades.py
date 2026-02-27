"""HTTP API layer: arcade list/detail read endpoints."""

from __future__ import annotations

from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_container
from app.core.container import AppContainer
from app.protocol.messages import ArcadeShopDetailDto, ArcadeShopSummaryDto, PagedArcadeResponse

router = APIRouter(prefix="/api/v1/arcades", tags=["arcades"])


def _summary_dto(raw: dict) -> ArcadeShopSummaryDto:
    return ArcadeShopSummaryDto(
        source=raw["source"],
        source_id=raw["source_id"],
        source_url=raw["source_url"],
        name=raw["name"],
        name_pinyin=raw.get("name_pinyin"),
        address=raw.get("address"),
        transport=raw.get("transport"),
        province_code=raw.get("province_code"),
        province_name=raw.get("province_name"),
        city_code=raw.get("city_code"),
        city_name=raw.get("city_name"),
        county_code=raw.get("county_code"),
        county_name=raw.get("county_name"),
        status=raw.get("status"),
        type=raw.get("type"),
        pay_type=raw.get("pay_type"),
        locked=raw.get("locked"),
        ea_status=raw.get("ea_status"),
        price=raw.get("price"),
        start_time=raw.get("start_time"),
        end_time=raw.get("end_time"),
        fav_count=raw.get("fav_count"),
        updated_at=raw.get("updated_at"),
        arcade_count=int(raw.get("arcade_count") or 0),
    )


@router.get("", response_model=PagedArcadeResponse)
def list_arcades(
    keyword: str | None = Query(default=None),
    province_code: str | None = Query(default=None),
    city_code: str | None = Query(default=None),
    county_code: str | None = Query(default=None),
    has_arcades: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    container: AppContainer = Depends(get_container),
) -> PagedArcadeResponse:
    rows, total = container.store.list_shops(
        keyword=keyword,
        province_code=province_code,
        city_code=city_code,
        county_code=county_code,
        has_arcades=has_arcades,
        page=page,
        page_size=page_size,
    )
    items = [_summary_dto(row) for row in rows]
    total_pages = ceil(total / page_size) if total > 0 else 0
    return PagedArcadeResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/{source_id}", response_model=ArcadeShopDetailDto)
def get_arcade_detail(
    source_id: int,
    container: AppContainer = Depends(get_container),
) -> ArcadeShopDetailDto:
    row = container.store.get_shop(source_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"arcade source_id={source_id} not found")
    return ArcadeShopDetailDto(
        source=row["source"],
        source_id=row["source_id"],
        source_url=row["source_url"],
        name=row["name"],
        name_pinyin=row.get("name_pinyin"),
        address=row.get("address"),
        transport=row.get("transport"),
        comment=row.get("comment"),
        url=row.get("url"),
        province_code=row.get("province_code"),
        province_name=row.get("province_name"),
        city_code=row.get("city_code"),
        city_name=row.get("city_name"),
        county_code=row.get("county_code"),
        county_name=row.get("county_name"),
        status=row.get("status"),
        type=row.get("type"),
        pay_type=row.get("pay_type"),
        locked=row.get("locked"),
        ea_status=row.get("ea_status"),
        price=row.get("price"),
        start_time=row.get("start_time"),
        end_time=row.get("end_time"),
        fav_count=row.get("fav_count"),
        updated_at=row.get("updated_at"),
        arcade_count=int(row.get("arcade_count") or 0),
        image_thumb=row.get("image_thumb"),
        events=row.get("events") or [],
        arcades=row.get("arcades") or [],
        collab=row.get("collab"),
        raw=row.get("raw"),
    )

