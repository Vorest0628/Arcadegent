"""Tool layer: DB-style read tool backed by local in-memory store."""

from __future__ import annotations

from typing import Any

from app.infra.db.local_store import LocalArcadeStore


class DBQueryTool:
    """Unified query interface used by orchestrator runtime."""

    def __init__(self, store: LocalArcadeStore) -> None:
        self._store = store

    def search_shops(
        self,
        *,
        keyword: str | None,
        province_code: str | None,
        city_code: str | None,
        county_code: str | None,
        province_name: str | None,
        city_name: str | None,
        county_name: str | None,
        has_arcades: bool | None,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        return self._store.list_shops(
            keyword=keyword,
            province_code=province_code,
            city_code=city_code,
            county_code=county_code,
            province_name=province_name,
            city_name=city_name,
            county_name=county_name,
            has_arcades=has_arcades,
            page=page,
            page_size=page_size,
        )

    def get_shop(self, source_id: int) -> dict[str, Any] | None:
        return self._store.get_shop(source_id)
