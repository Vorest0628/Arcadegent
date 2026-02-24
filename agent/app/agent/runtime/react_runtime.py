"""ReAct runtime: model tool-loop with session-level state accumulation."""

from __future__ import annotations

import json
import re
from uuid import uuid4

from app.agent.context.context_builder import ContextBuilder
from app.agent.events.replay_buffer import ReplayBuffer
from app.agent.llm.provider_adapter import ModelToolCall, ProviderAdapter
from app.agent.orchestration.transition_policy import TransitionPolicy
from app.agent.runtime.loop_guard import LoopGuard
from app.agent.runtime.session_state import AgentSessionState, AgentTurn, SessionStateStore
from app.agent.subagents.subagent_builder import SubAgentBuilder
from app.agent.tools.registry import ToolExecutionResult, ToolRegistry
from app.protocol.messages import (
    ArcadeShopSummaryDto,
    ChatRequest,
    ChatResponse,
    IntentType,
    RouteSummaryDto,
)


def _infer_intent(message: str) -> IntentType:
    text = message.strip().lower()
    if re.search(r"\u5bfc\u822a|\u8def\u7ebf|\u600e\u4e48\u53bb|how to go|route|go to", text):
        return "navigate"
    if re.search(r"\u9644\u8fd1|nearby|near", text):
        return "search_nearby"
    return "search"


def _normalize_intent(raw: str | None) -> IntentType:
    if raw == "navigate":
        return "navigate"
    if raw == "search_nearby":
        return "search_nearby"
    return "search"


def _extract_keyword(message: str) -> str:
    text = message.strip()
    if not text:
        return ""
    latin_matches = re.findall(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,40}", text)
    if latin_matches:
        candidate = latin_matches[-1].strip()
        if " " in candidate:
            pieces = [item for item in re.split(r"\s+", candidate) if item]
            if pieces:
                candidate = pieces[-1]
        return candidate
    cleaned = re.sub(
        r"(\u5e2e\u6211\u627e|\u8bf7\u5e2e\u6211\u627e|\u5e2e\u5fd9\u627e|\u9644\u8fd1\u54ea\u91cc\u6709|\u9644\u8fd1\u6709\u6ca1\u6709|\u6709\u6ca1\u6709|\u627e\u4e00\u4e0b|\u67e5\u4e00\u4e0b|\u641c\u7d22|\u67e5\u8be2|\u673a\u5385)",
        " ",
        text,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.!?\uFF0C\u3002\uFF01\uFF1F")
    return cleaned or text


def _summary_row(raw: dict) -> ArcadeShopSummaryDto:
    return ArcadeShopSummaryDto(
        source=str(raw.get("source") or ""),
        source_id=int(raw.get("source_id") or 0),
        source_url=str(raw.get("source_url") or ""),
        name=str(raw.get("name") or "unknown arcade"),
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


class ReactRuntime:
    """Function-calling ReAct orchestrator with in-memory session persistence."""

    def __init__(
        self,
        *,
        context_builder: ContextBuilder,
        subagent_builder: SubAgentBuilder,
        tool_registry: ToolRegistry,
        provider_adapter: ProviderAdapter,
        session_store: SessionStateStore,
        transition_policy: TransitionPolicy,
        replay_buffer: ReplayBuffer,
        max_steps: int,
    ) -> None:
        self._context_builder = context_builder
        self._subagent_builder = subagent_builder
        self._tool_registry = tool_registry
        self._provider_adapter = provider_adapter
        self._session_store = session_store
        self._transition_policy = transition_policy
        self._replay_buffer = replay_buffer
        self._max_steps = max(2, max_steps)

    def run_chat(self, request: ChatRequest) -> ChatResponse:
        session_id = request.session_id or f"s_{uuid4().hex[:12]}"
        state = self._session_store.get_or_create(session_id)
        state.turn_index += 1

        inferred_intent = request.intent or _infer_intent(request.message)
        if request.intent is not None:
            state.intent = request.intent
        elif inferred_intent in {"navigate", "search_nearby"}:
            state.intent = inferred_intent
        elif not state.intent:
            state.intent = inferred_intent

        state.active_subagent = "intent_router"

        request_payload = request.model_dump(mode="json")
        state.working_memory["last_request"] = request_payload
        if request.shop_id is not None:
            state.working_memory["last_shop_id"] = request.shop_id
        if request.keyword:
            state.working_memory["keyword"] = request.keyword
        else:
            state.working_memory["keyword"] = _extract_keyword(request.message)

        self._append_turn(
            state,
            AgentTurn(
                role="user",
                content=request.message,
                payload=request_payload,
            ),
        )
        self._replay_buffer.append(
            session_id,
            "session.started",
            {
                "intent": state.intent,
                "model": "react-runtime",
                "active_subagent": state.active_subagent,
            },
        )

        guard = LoopGuard(self._max_steps)
        final_text: str | None = None
        while not guard.exhausted:
            guard.next()
            subagent = self._subagent_builder.get(state.active_subagent)
            context = self._context_builder.build(
                session_state=state,
                request=request,
                subagent=subagent,
            )
            model_response = self._provider_adapter.complete(
                instructions=context.instructions,
                messages=context.messages,
                tools=self._tool_registry.tool_definitions(allowed_tools=subagent.allowed_tools),
                runtime_hints={
                    "active_subagent": state.active_subagent,
                    "intent": state.intent,
                    "request": request_payload,
                    "memory": state.working_memory,
                },
            )
            if model_response.response_id:
                state.previous_response_id = model_response.response_id

            if model_response.tool_calls:
                terminal_after_tools = self._execute_tool_calls(
                    session_id=session_id,
                    state=state,
                    tool_calls=model_response.tool_calls,
                    allowed_tools=subagent.allowed_tools,
                )
                if terminal_after_tools:
                    final_text = str(state.working_memory.get("reply") or "")
                    break
                continue

            if model_response.text:
                final_text = model_response.text
                break

            if state.working_memory.get("reply"):
                final_text = str(state.working_memory.get("reply"))
                break

        if not final_text:
            final_text = self._fallback_reply(state, request)

        self._append_turn(
            state,
            AgentTurn(
                role="assistant",
                content=final_text,
                payload={"final": True},
            ),
        )
        state.working_memory["reply"] = final_text
        self._replay_buffer.append(session_id, "assistant.completed", {"reply": final_text})
        return self._build_response(session_id=session_id, state=state, final_text=final_text)

    def _execute_tool_calls(
        self,
        *,
        session_id: str,
        state: AgentSessionState,
        tool_calls: list[ModelToolCall],
        allowed_tools: list[str],
    ) -> bool:
        terminal = False
        for call in tool_calls:
            self._replay_buffer.append(
                session_id,
                "tool.started",
                {"tool": call.name, "call_id": call.call_id},
            )
            result = self._tool_registry.execute(
                call_id=call.call_id,
                tool_name=call.name,
                raw_arguments=call.arguments,
                allowed_tools=allowed_tools,
            )
            self._record_tool_result(session_id=session_id, state=state, result=result)
            if self._transition_policy.is_terminal_tool(
                tool_name=result.tool_name,
                tool_status=result.status,
            ):
                terminal = True
        return terminal

    def _record_tool_result(
        self,
        *,
        session_id: str,
        state: AgentSessionState,
        result: ToolExecutionResult,
    ) -> None:
        if result.status == "completed":
            completed_payload = {
                "tool": result.tool_name,
                "call_id": result.call_id,
            }
            if result.tool_name == "route_plan_tool":
                route = result.output.get("route")
                if isinstance(route, dict):
                    completed_payload["distance_m"] = route.get("distance_m")
                    self._replay_buffer.append(session_id, "navigation.route_ready", route)
            self._replay_buffer.append(session_id, "tool.completed", completed_payload)
        else:
            self._replay_buffer.append(
                session_id,
                "tool.failed",
                {
                    "tool": result.tool_name,
                    "call_id": result.call_id,
                    "error": result.error_message or "tool execution failed",
                },
            )

        self._append_turn(
            state,
            AgentTurn(
                role="tool",
                name=result.tool_name,
                call_id=result.call_id,
                content=json.dumps(result.output, ensure_ascii=False),
                payload={"status": result.status, "result": result.output},
            ),
        )

        self._apply_tool_memory(state=state, result=result)
        state.active_subagent = self._transition_policy.next_subagent(
            current_subagent=state.active_subagent,
            tool_name=result.tool_name,
            tool_status=result.status,
            tool_output=result.output,
            fallback_intent=state.intent,
        )

    def _apply_tool_memory(self, *, state: AgentSessionState, result: ToolExecutionResult) -> None:
        if result.tool_name == "select_next_subagent" and result.status == "completed":
            next_subagent = result.output.get("next_subagent")
            if isinstance(next_subagent, str) and next_subagent:
                state.active_subagent = next_subagent
            next_intent = result.output.get("intent")
            if isinstance(next_intent, str):
                state.intent = _normalize_intent(next_intent)
            return

        if result.status != "completed":
            state.working_memory["last_error"] = result.output.get("error")
            return

        if result.tool_name == "db_query_tool":
            shop_payload = result.output.get("shop")
            if isinstance(shop_payload, dict):
                state.working_memory["shop"] = shop_payload
                source_id = shop_payload.get("source_id")
                if source_id is not None:
                    state.working_memory["last_shop_id"] = source_id
                return
            shops = result.output.get("shops")
            if isinstance(shops, list):
                state.working_memory["shops"] = shops
                if shops:
                    first = shops[0] if isinstance(shops[0], dict) else None
                    if isinstance(first, dict) and first.get("source_id") is not None:
                        state.working_memory["last_shop_id"] = first.get("source_id")
            total = result.output.get("total")
            if total is not None:
                state.working_memory["total"] = int(total)
            last_request = state.working_memory.get("last_request")
            if isinstance(last_request, dict):
                state.working_memory["keyword"] = last_request.get("keyword") or _extract_keyword(
                    str(last_request.get("message") or "")
                )
            return

        if result.tool_name == "geo_resolve_tool":
            provider = result.output.get("provider")
            if isinstance(provider, str):
                state.working_memory["provider"] = provider
            return

        if result.tool_name == "route_plan_tool":
            route = result.output.get("route")
            if isinstance(route, dict):
                state.working_memory["route"] = route
                state.intent = "navigate"
            return

        if result.tool_name == "summary_tool":
            reply = result.output.get("reply")
            if isinstance(reply, str) and reply.strip():
                state.working_memory["reply"] = reply.strip()
            return

    def _fallback_reply(self, state: AgentSessionState, request: ChatRequest) -> str:
        reply = state.working_memory.get("reply")
        if isinstance(reply, str) and reply.strip():
            return reply.strip()

        if _normalize_intent(state.intent) == "navigate":
            if state.working_memory.get("route"):
                return "route is ready, retry once to get a complete summary."
            if request.shop_id is None and state.working_memory.get("last_shop_id") is None:
                return "please provide shop_id before asking for navigation."
            return "navigation flow is incomplete, please retry."

        shops_payload = state.working_memory.get("shops")
        if isinstance(shops_payload, list) and shops_payload:
            top = shops_payload[0] if isinstance(shops_payload[0], dict) else None
            if isinstance(top, dict):
                return f"matched arcades found, start with {top.get('name') or 'unknown arcade'}."
        return "request received but no sufficient result, try another keyword."

    def _build_response(self, *, session_id: str, state: AgentSessionState, final_text: str) -> ChatResponse:
        shops_raw: list[dict] = []
        memory_shops = state.working_memory.get("shops")
        if isinstance(memory_shops, list):
            shops_raw.extend(item for item in memory_shops if isinstance(item, dict))
        memory_shop = state.working_memory.get("shop")
        if isinstance(memory_shop, dict):
            source_id = memory_shop.get("source_id")
            exists = any(item.get("source_id") == source_id for item in shops_raw)
            if not exists:
                shops_raw.append(memory_shop)
        shops = [_summary_row(row) for row in shops_raw[:20]]

        route_obj: RouteSummaryDto | None = None
        memory_route = state.working_memory.get("route")
        if isinstance(memory_route, dict):
            try:
                route_obj = RouteSummaryDto.model_validate(memory_route)
            except Exception:
                route_obj = None

        intent = _normalize_intent(state.intent)
        if route_obj is not None:
            intent = "navigate"
        return ChatResponse(
            session_id=session_id,
            intent=intent,
            reply=final_text,
            shops=shops,
            route=route_obj,
        )

    def _append_turn(self, state: AgentSessionState, turn: AgentTurn) -> None:
        state.turns.append(turn)
