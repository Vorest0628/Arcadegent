"""Executor for the builtin arcade search tool."""

from __future__ import annotations

import re
from typing import Any

from app.agent.tools.builtin.executor_utils import as_region_code_or_name, short_text
from app.agent.tools.builtin.provider import BuiltinToolContext
from app.infra.observability.logger import get_logger

logger = get_logger(__name__)


def execute(context: BuiltinToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Normalize region filters and execute the store-backed shop query."""
    tool = context.require("db_query_tool")

    shop_id = args.get("shop_id")
    if shop_id is not None:
        return {"shop": tool.get_shop(shop_id)}

    province_code, province_name = as_region_code_or_name(
        args.get("province_code"),
        args.get("province_name"),
    )
    city_code, city_name = as_region_code_or_name(
        args.get("city_code"),
        args.get("city_name"),
    )
    county_code, county_name = as_region_code_or_name(
        args.get("county_code"),
        args.get("county_name"),
    )

    sort_by = str(args.get("sort_by") or "default")
    sort_order = str(args.get("sort_order") or "desc")
    sort_title_name = args.get("sort_title_name")
    if sort_by == "title_quantity" and not (sort_title_name or "").strip():
        keyword = (args.get("keyword") or "").strip()
        if keyword:
            parts = [part for part in re.split(r"\s+", keyword) if part]
            if parts:
                sort_title_name = parts[-1]

    rows, total = tool.search_shops(
        keyword=args.get("keyword"),
        province_code=province_code,
        city_code=city_code,
        county_code=county_code,
        province_name=province_name,
        city_name=city_name,
        county_name=county_name,
        has_arcades=args.get("has_arcades"),
        page=int(args["page"]),
        page_size=int(args["page_size"]),
        sort_by=sort_by,
        sort_order=sort_order,
        sort_title_name=sort_title_name,
    )
    logger.info(
        "db_query_tool.filters keyword=%s province_code=%s city_code=%s county_code=%s province_name=%s city_name=%s county_name=%s has_arcades=%s sort_by=%s sort_order=%s sort_title_name=%s page=%s page_size=%s total=%s",
        short_text(args.get("keyword")),
        province_code,
        city_code,
        county_code,
        province_name,
        city_name,
        county_name,
        args.get("has_arcades"),
        sort_by,
        sort_order,
        short_text(sort_title_name),
        args["page"],
        args["page_size"],
        total,
    )
    return {
        "shops": rows,
        "total": total,
        "query": {
            "keyword": args.get("keyword"),
            "province_code": province_code,
            "city_code": city_code,
            "county_code": county_code,
            "province_name": province_name,
            "city_name": city_name,
            "county_name": county_name,
            "has_arcades": args.get("has_arcades"),
            "sort_by": sort_by,
            "sort_order": sort_order,
            "sort_title_name": sort_title_name,
            "page": args["page"],
            "page_size": args["page_size"],
        },
    }
