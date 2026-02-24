"""Unified tool registry with schema validation and execution dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.agent.tools.builtin.db_query_tool import DBQueryTool
from app.agent.tools.builtin.geo_resolve_tool import GeoResolveTool
from app.agent.tools.builtin.route_plan_tool import RoutePlanTool
from app.agent.tools.builtin.select_next_subagent_tool import SelectNextSubagentTool
from app.agent.tools.builtin.summary_tool import SummaryTool
from app.agent.tools.permission import ToolPermissionChecker, ToolPermissionError
from app.agent.tools.schemas import (
    DBQueryArgs,
    GeoResolveArgs,
    RoutePlanArgs,
    SelectNextSubagentArgs,
    SummaryArgs,
    TOOL_ARG_MODELS,
    build_tool_definitions,
)
from app.protocol.messages import Location, RouteSummaryDto


@dataclass(frozen=True)
class ToolExecutionResult:
    """Normalized tool execution output."""

    call_id: str
    tool_name: str
    status: str
    output: dict[str, Any]
    error_message: str | None = None


class ToolRegistry:
    """Schema-first runtime entrypoint for builtin tools."""

    def __init__(
        self,
        *,
        db_query_tool: DBQueryTool,
        geo_resolve_tool: GeoResolveTool,
        route_plan_tool: RoutePlanTool,
        summary_tool: SummaryTool,
        select_next_subagent_tool: SelectNextSubagentTool,
        permission_checker: ToolPermissionChecker,
        strict_schema: bool = True,
    ) -> None:
        self._db_query_tool = db_query_tool
        self._geo_resolve_tool = geo_resolve_tool
        self._route_plan_tool = route_plan_tool
        self._summary_tool = summary_tool
        self._select_next_subagent_tool = select_next_subagent_tool
        self._permission_checker = permission_checker
        self._strict_schema = strict_schema

    def tool_definitions(self, *, allowed_tools: list[str]) -> list[dict[str, Any]]:
        return build_tool_definitions(allowed_tools, strict=self._strict_schema)

    def execute(
        self,
        *,
        call_id: str,
        tool_name: str,
        raw_arguments: dict[str, Any],
        allowed_tools: list[str],
    ) -> ToolExecutionResult:
        try:
            self._permission_checker.ensure_allowed(tool_name=tool_name, allowed_tools=allowed_tools)
            validated = self._validate_arguments(tool_name=tool_name, raw_arguments=raw_arguments)
            output = self._dispatch(tool_name=tool_name, validated=validated)
            return ToolExecutionResult(
                call_id=call_id,
                tool_name=tool_name,
                status="completed",
                output=output,
            )
        except ToolPermissionError as exc:
            return self._failed(
                call_id=call_id,
                tool_name=tool_name,
                error_type="permission_error",
                message=str(exc),
            )
        except ValidationError as exc:
            return self._failed(
                call_id=call_id,
                tool_name=tool_name,
                error_type="validation_error",
                message=str(exc),
                details=exc.errors(),
            )
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            return self._failed(
                call_id=call_id,
                tool_name=tool_name,
                error_type="runtime_error",
                message=str(exc),
            )

    def _validate_arguments(self, *, tool_name: str, raw_arguments: dict[str, Any]) -> Any:
        model = TOOL_ARG_MODELS.get(tool_name)
        if model is None:
            raise ValueError(f"unknown_tool:{tool_name}")
        return model.model_validate(raw_arguments)

    def _dispatch(self, *, tool_name: str, validated: Any) -> dict[str, Any]:
        if tool_name == "db_query_tool":
            args = validated if isinstance(validated, DBQueryArgs) else DBQueryArgs.model_validate(validated)
            if args.shop_id is not None:
                shop = self._db_query_tool.get_shop(args.shop_id)
                return {"shop": shop}
            rows, total = self._db_query_tool.search_shops(
                keyword=args.keyword,
                province_code=args.province_code,
                city_code=args.city_code,
                county_code=args.county_code,
                has_arcades=args.has_arcades,
                page=args.page,
                page_size=args.page_size,
            )
            return {"shops": rows, "total": total}

        if tool_name == "geo_resolve_tool":
            args = validated if isinstance(validated, GeoResolveArgs) else GeoResolveArgs.model_validate(validated)
            provider = self._geo_resolve_tool.resolve_provider(args.province_code)
            return {"provider": provider}

        if tool_name == "route_plan_tool":
            args = validated if isinstance(validated, RoutePlanArgs) else RoutePlanArgs.model_validate(validated)
            route = self._route_plan_tool.plan_route(
                provider=args.provider,
                mode=args.mode,
                origin=Location(lng=args.origin.lng, lat=args.origin.lat),
                destination=Location(lng=args.destination.lng, lat=args.destination.lat),
            )
            return {"route": route.model_dump(mode="json")}

        if tool_name == "summary_tool":
            args = validated if isinstance(validated, SummaryArgs) else SummaryArgs.model_validate(validated)
            if args.topic == "navigation":
                route_payload = args.route or {}
                route = RouteSummaryDto.model_validate(route_payload)
                reply = self._summary_tool.summarize_navigation(
                    shop_name=args.shop_name or "target arcade",
                    route=route,
                )
            else:
                reply = self._summary_tool.summarize_search(
                    keyword=args.keyword,
                    total=int(args.total or 0),
                    shops=args.shops or [],
                )
            return {"reply": reply}

        if tool_name == "select_next_subagent":
            args = (
                validated
                if isinstance(validated, SelectNextSubagentArgs)
                else SelectNextSubagentArgs.model_validate(validated)
            )
            return self._select_next_subagent_tool.select_next_subagent(
                current_subagent=args.current_subagent,
                intent=args.intent,
                tool_name=args.tool_name,
                tool_status=args.tool_status,
                has_route=args.has_route,
                has_shops=args.has_shops,
            )

        raise ValueError(f"unknown_tool:{tool_name}")

    def _failed(
        self,
        *,
        call_id: str,
        tool_name: str,
        error_type: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
    ) -> ToolExecutionResult:
        payload: dict[str, Any] = {
            "error": {
                "type": error_type,
                "message": message,
            }
        }
        if details is not None:
            payload["error"]["details"] = details
        return ToolExecutionResult(
            call_id=call_id,
            tool_name=tool_name,
            status="failed",
            output=payload,
            error_message=message,
        )

