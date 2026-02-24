"""Unit tests for local JSONL-backed store filtering and region indexes."""

from __future__ import annotations

import json
from pathlib import Path

from app.infra.db.local_store import LocalArcadeStore


def _write_rows(path: Path) -> None:
    rows = [
        {
            "source": "bemanicn",
            "source_id": 1,
            "source_url": "https://map.bemanicn.com/s/1",
            "name": "Alpha Arcade",
            "name_pinyin": "alpha",
            "address": "Addr A",
            "province_code": "110000000000",
            "province_name": "Beijing",
            "city_code": "110100000000",
            "city_name": "Beijing",
            "county_code": "110101000000",
            "county_name": "Dongcheng",
            "updated_at": "2026-02-20T00:00:00Z",
            "arcades": [{"title_name": "maimai", "quantity": 2}],
        },
        {
            "source": "bemanicn",
            "source_id": 2,
            "source_url": "https://map.bemanicn.com/s/2",
            "name": "Beta",
            "address": "Addr B",
            "province_code": "310000000000",
            "province_name": "Shanghai",
            "city_code": "310100000000",
            "city_name": "Shanghai",
            "county_code": "310101000000",
            "county_name": "Huangpu",
            "updated_at": "2026-02-19T00:00:00Z",
            "arcades": [],
        },
    ]
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def test_filter_by_keyword_and_region(tmp_path: Path) -> None:
    data_path = tmp_path / "shops.jsonl"
    _write_rows(data_path)
    store = LocalArcadeStore.from_jsonl(data_path)

    page, total = store.list_shops(
        keyword="maimai",
        province_code="110000000000",
        city_code=None,
        county_code=None,
        has_arcades=True,
        page=1,
        page_size=10,
    )
    assert total == 1
    assert page[0]["source_id"] == 1


def test_regions_index(tmp_path: Path) -> None:
    data_path = tmp_path / "shops.jsonl"
    _write_rows(data_path)
    store = LocalArcadeStore.from_jsonl(data_path)

    provinces = store.list_provinces()
    assert {row["code"] for row in provinces} == {"110000000000", "310000000000"}

    cities = store.list_cities("110000000000")
    assert len(cities) == 1
    assert cities[0]["name"] == "Beijing"
