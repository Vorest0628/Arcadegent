"""Unit tests for tool registry validation and dispatch behavior."""

from __future__ import annotations

import json
from pathlib import Path

from app.agent.tools.builtin.db_query_tool import DBQueryTool
from app.agent.tools.builtin.geo_resolve_tool import GeoResolveTool
from app.agent.tools.builtin.route_plan_tool import RoutePlanTool
from app.agent.tools.builtin.select_next_subagent_tool import SelectNextSubagentTool
from app.agent.tools.builtin.summary_tool import SummaryTool
from app.agent.tools.permission import ToolPermissionChecker
from app.agent.tools.registry import ToolRegistry
from app.infra.db.local_store import LocalArcadeStore


def _write_rows(path: Path) -> None:
    rows = [
        {
            "source": "bemanicn",
            "source_id": 1,
            "source_url": "https://map.bemanicn.com/s/1",
            "name": "Alpha Arcade",
            "province_code": "110000000000",
            "province_name": "Beijing",
            "city_code": "110100000000",
            "city_name": "Beijing",
            "county_code": "110101000000",
            "county_name": "Dongcheng",
            "arcades": [{"title_name": "maimai", "quantity": 2}],
        }
    ]
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _build_registry(tmp_path: Path) -> ToolRegistry:
    data_path = tmp_path / "shops.jsonl"
    _write_rows(data_path)
    store = LocalArcadeStore.from_jsonl(data_path)
    return ToolRegistry(
        db_query_tool=DBQueryTool(store),
        geo_resolve_tool=GeoResolveTool(),
        route_plan_tool=RoutePlanTool(),
        summary_tool=SummaryTool(),
        select_next_subagent_tool=SelectNextSubagentTool(),
        permission_checker=ToolPermissionChecker(policy_file=tmp_path / "missing.yaml"),
        strict_schema=True,
    )


def test_tool_registry_returns_validation_error_for_bad_args(tmp_path: Path) -> None:
    registry = _build_registry(tmp_path)
    result = registry.execute(
        call_id="c1",
        tool_name="route_plan_tool",
        raw_arguments={
            "provider": "amap",
            "mode": "walking",
            "origin": {"lng": 116.3, "lat": 39.9},
            "destination": {"lng": 116.4},
        },
        allowed_tools=["route_plan_tool"],
    )
    assert result.status == "failed"
    assert result.output["error"]["type"] == "validation_error"


def test_tool_registry_can_lookup_one_shop(tmp_path: Path) -> None:
    registry = _build_registry(tmp_path)
    result = registry.execute(
        call_id="c2",
        tool_name="db_query_tool",
        raw_arguments={
            "keyword": None,
            "province_code": None,
            "city_code": None,
            "county_code": None,
            "has_arcades": None,
            "page": 1,
            "page_size": 1,
            "shop_id": 1,
        },
        allowed_tools=["db_query_tool"],
    )
    assert result.status == "completed"
    assert result.output["shop"]["source_id"] == 1


def test_tool_registry_normalizes_city_name_in_city_code_field(tmp_path: Path) -> None:
    registry = _build_registry(tmp_path)
    result = registry.execute(
        call_id="c3",
        tool_name="db_query_tool",
        raw_arguments={
            "keyword": "maimai",
            "province_code": None,
            "city_code": "Beijing",
            "county_code": None,
            "province_name": None,
            "city_name": None,
            "county_name": None,
            "has_arcades": True,
            "page": 1,
            "page_size": 10,
            "shop_id": None,
        },
        allowed_tools=["db_query_tool"],
    )
    assert result.status == "completed"
    assert result.output["total"] == 1
    assert result.output["shops"][0]["source_id"] == 1
