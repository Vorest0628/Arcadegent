"""Provider adapter with responses/chat-completions dual stack and offline planner."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib import error, request
from uuid import uuid4

from app.agent.llm.llm_config import LLMConfig
from app.protocol.messages import IntentType


def _safe_json_loads(raw: str | bytes | None) -> dict[str, Any]:
    if raw is None:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _infer_intent(message: str) -> IntentType:
    text = message.strip().lower()
    if re.search(r"\u5bfc\u822a|\u8def\u7ebf|\u600e\u4e48\u53bb|how to go|route|go to", text):
        return "navigate"
    if re.search(r"\u9644\u8fd1|nearby|near", text):
        return "search_nearby"
    return "search"


def _looks_like_followup(message: str) -> bool:
    text = message.strip().lower()
    if not text:
        return False
    followup_patterns = (
        r"\u7ee7\u7eed",
        r"\u518d(\u8bf4|\u603b\u7ed3|\u7ed9)",
        r"\u4e0a\u6b21",
        r"\u524d\u9762",
        r"\u7ee7\u7eed\u4e00\u4e0b",
        r"continue",
        r"follow up",
    )
    return any(re.search(pattern, text) for pattern in followup_patterns)


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


@dataclass(frozen=True)
class ModelToolCall:
    """Normalized function call emitted by model/offline planner."""

    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelResponse:
    """Normalized model response with optional tool calls."""

    text: str | None = None
    tool_calls: list[ModelToolCall] = field(default_factory=list)
    reasoning_items: list[dict[str, Any]] = field(default_factory=list)
    response_id: str | None = None


class ProviderAdapter:
    """Execute one model turn against OpenAI-compatible provider."""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def complete(
        self,
        *,
        instructions: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        runtime_hints: dict[str, Any] | None = None,
    ) -> ModelResponse:
        hints = runtime_hints or {}
        if not self.enabled:
            return self._offline_complete(tools=tools, runtime_hints=hints)

        by_responses = self._try_responses_api(
            instructions=instructions,
            messages=messages,
            tools=tools,
        )
        if by_responses is not None:
            return by_responses

        by_chat = self._try_chat_completions(
            instructions=instructions,
            messages=messages,
            tools=tools,
        )
        if by_chat is not None:
            return by_chat

        return self._offline_complete(tools=tools, runtime_hints=hints)

    def _post_json(self, *, endpoint: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with request.urlopen(req, timeout=self._config.timeout_seconds) as resp:
                return _safe_json_loads(resp.read().decode("utf-8", errors="replace"))
        except (error.URLError, error.HTTPError, TimeoutError):
            return None

    def _try_responses_api(
        self,
        *,
        instructions: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse | None:
        endpoint = self._config.base_url.rstrip("/") + "/responses"
        payload: dict[str, Any] = {
            "model": self._config.model,
            "instructions": instructions,
            "input": messages,
            "temperature": self._config.temperature,
            "max_output_tokens": self._config.max_tokens,
            "tool_choice": self._config.tool_choice,
            "parallel_tool_calls": self._config.parallel_tool_calls,
        }
        if tools:
            payload["tools"] = [self._to_responses_tool(tool) for tool in tools]

        decoded = self._post_json(endpoint=endpoint, payload=payload)
        if not isinstance(decoded, dict):
            return None

        tool_calls: list[ModelToolCall] = []
        reasoning: list[dict[str, Any]] = []
        text_chunks: list[str] = []
        output = decoded.get("output")
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, dict):
                    continue
                item_type = str(item.get("type") or "")
                if item_type == "function_call":
                    tool_call = self._parse_responses_tool_call(item)
                    if tool_call:
                        tool_calls.append(tool_call)
                    continue
                if item_type == "reasoning":
                    reasoning.append(item)
                    continue
                if item_type == "message":
                    text_chunks.extend(self._extract_responses_message_text(item))
                    continue
                if item_type == "output_text":
                    chunk = str(item.get("text") or "").strip()
                    if chunk:
                        text_chunks.append(chunk)

        if not text_chunks:
            output_text = decoded.get("output_text")
            if isinstance(output_text, str) and output_text.strip():
                text_chunks.append(output_text.strip())

        text = "\n".join(chunk for chunk in text_chunks if chunk).strip() or None
        if text is None and not tool_calls and not reasoning:
            return None

        response_id = decoded.get("id")
        return ModelResponse(
            text=text,
            tool_calls=tool_calls,
            reasoning_items=reasoning,
            response_id=str(response_id) if response_id is not None else None,
        )

    def _to_responses_tool(self, tool: dict[str, Any]) -> dict[str, Any]:
        if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
            function = tool["function"]
            payload = {
                "type": "function",
                "name": function.get("name"),
                "description": function.get("description"),
                "parameters": function.get("parameters"),
            }
            if "strict" in function:
                payload["strict"] = function.get("strict")
            return payload
        return tool

    def _parse_responses_tool_call(self, payload: dict[str, Any]) -> ModelToolCall | None:
        name = payload.get("name")
        if not isinstance(name, str) or not name:
            return None
        raw_args = payload.get("arguments")
        if isinstance(raw_args, str):
            args = _safe_json_loads(raw_args)
        elif isinstance(raw_args, dict):
            args = raw_args
        else:
            args = {}
        call_id = payload.get("call_id") or payload.get("id") or f"call_{uuid4().hex[:12]}"
        return ModelToolCall(call_id=str(call_id), name=name, arguments=args)

    def _extract_responses_message_text(self, message_item: dict[str, Any]) -> list[str]:
        chunks: list[str] = []
        content = message_item.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and str(part.get("type")) == "output_text":
                    text = str(part.get("text") or "").strip()
                    if text:
                        chunks.append(text)
        return chunks

    def _try_chat_completions(
        self,
        *,
        instructions: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse | None:
        endpoint = self._config.base_url.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": [{"role": "system", "content": instructions}] + messages,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "tool_choice": self._config.tool_choice,
            "parallel_tool_calls": self._config.parallel_tool_calls,
        }
        if tools:
            payload["tools"] = tools

        decoded = self._post_json(endpoint=endpoint, payload=payload)
        if not isinstance(decoded, dict):
            return None
        choices = decoded.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first, dict) else None
        if not isinstance(message, dict):
            return None

        text = self._extract_chat_text(message.get("content"))
        tool_calls: list[ModelToolCall] = []
        raw_tool_calls = message.get("tool_calls")
        if isinstance(raw_tool_calls, list):
            for raw_call in raw_tool_calls:
                parsed = self._parse_chat_tool_call(raw_call)
                if parsed:
                    tool_calls.append(parsed)

        if text is None and not tool_calls:
            return None
        return ModelResponse(text=text, tool_calls=tool_calls, reasoning_items=[])

    def _extract_chat_text(self, raw_content: Any) -> str | None:
        if isinstance(raw_content, str):
            text = raw_content.strip()
            return text or None
        if isinstance(raw_content, list):
            chunks: list[str] = []
            for item in raw_content:
                if not isinstance(item, dict):
                    continue
                item_type = str(item.get("type") or "")
                if item_type not in {"text", "output_text"}:
                    continue
                value = str(item.get("text") or item.get("value") or "").strip()
                if value:
                    chunks.append(value)
            merged = "\n".join(chunks).strip()
            return merged or None
        return None

    def _parse_chat_tool_call(self, raw_call: Any) -> ModelToolCall | None:
        if not isinstance(raw_call, dict):
            return None
        call_id = raw_call.get("id") or f"call_{uuid4().hex[:12]}"
        function = raw_call.get("function")
        if not isinstance(function, dict):
            return None
        name = function.get("name")
        if not isinstance(name, str) or not name:
            return None
        args_raw = function.get("arguments")
        if isinstance(args_raw, str):
            args = _safe_json_loads(args_raw)
        elif isinstance(args_raw, dict):
            args = args_raw
        else:
            args = {}
        return ModelToolCall(call_id=str(call_id), name=name, arguments=args)

    def _offline_complete(
        self,
        *,
        tools: list[dict[str, Any]],
        runtime_hints: dict[str, Any],
    ) -> ModelResponse:
        request_payload = runtime_hints.get("request")
        request_data = request_payload if isinstance(request_payload, dict) else {}
        memory_payload = runtime_hints.get("memory")
        memory = memory_payload if isinstance(memory_payload, dict) else {}
        message = str(request_data.get("message") or "")
        intent = str(runtime_hints.get("intent") or _infer_intent(message))
        active_subagent = str(runtime_hints.get("active_subagent") or "intent_router")

        available_tools = self._tool_name_set(tools)
        if active_subagent == "intent_router" and "select_next_subagent" in available_tools:
            return self._single_tool_call(
                name="select_next_subagent",
                arguments={
                    "current_subagent": "intent_router",
                    "intent": intent,
                    "tool_name": None,
                    "tool_status": "completed",
                    "has_route": bool(memory.get("route")),
                    "has_shops": bool(memory.get("shops")),
                },
            )

        if active_subagent == "search_agent":
            if (
                "summary_tool" in available_tools
                and bool(memory.get("shops"))
                and _looks_like_followup(message)
            ):
                return self._single_tool_call(
                    name="summary_tool",
                    arguments={
                        "topic": "search",
                        "keyword": memory.get("keyword"),
                        "total": memory.get("total"),
                        "shops": memory.get("shops"),
                        "shop_name": None,
                        "route": None,
                    },
                )
            if "db_query_tool" in available_tools:
                return self._single_tool_call(
                    name="db_query_tool",
                    arguments={
                        "keyword": request_data.get("keyword") or _extract_keyword(message),
                        "province_code": request_data.get("province_code"),
                        "city_code": request_data.get("city_code"),
                        "county_code": request_data.get("county_code"),
                        "has_arcades": True if intent == "search_nearby" else None,
                        "page": 1,
                        "page_size": int(request_data.get("page_size") or 5),
                        "shop_id": None,
                    },
                )
            if "summary_tool" in available_tools:
                return self._single_tool_call(
                    name="summary_tool",
                    arguments={
                        "topic": "search",
                        "keyword": request_data.get("keyword") or _extract_keyword(message),
                        "total": memory.get("total"),
                        "shops": memory.get("shops"),
                        "shop_name": None,
                        "route": None,
                    },
                )

        if active_subagent == "navigation_agent":
            if "db_query_tool" in available_tools and request_data.get("shop_id") is not None and not memory.get("shop"):
                return self._single_tool_call(
                    name="db_query_tool",
                    arguments={
                        "keyword": None,
                        "province_code": None,
                        "city_code": None,
                        "county_code": None,
                        "has_arcades": None,
                        "page": 1,
                        "page_size": 1,
                        "shop_id": int(request_data["shop_id"]),
                    },
                )
            if "geo_resolve_tool" in available_tools and not memory.get("provider"):
                shop = memory.get("shop") if isinstance(memory.get("shop"), dict) else {}
                return self._single_tool_call(
                    name="geo_resolve_tool",
                    arguments={
                        "province_code": shop.get("province_code") or request_data.get("province_code"),
                    },
                )
            if "route_plan_tool" in available_tools and not memory.get("route"):
                shop = memory.get("shop") if isinstance(memory.get("shop"), dict) else {}
                location = request_data.get("location")
                origin = location if isinstance(location, dict) else {"lng": 116.397428, "lat": 39.90923}
                lng = shop.get("longitude_wgs84") or shop.get("longitude_gcj02") or origin.get("lng")
                lat = shop.get("latitude_wgs84") or shop.get("latitude_gcj02") or origin.get("lat")
                return self._single_tool_call(
                    name="route_plan_tool",
                    arguments={
                        "provider": memory.get("provider") or "none",
                        "mode": "walking",
                        "origin": {"lng": float(origin["lng"]), "lat": float(origin["lat"])},
                        "destination": {"lng": float(lng), "lat": float(lat)},
                    },
                )
            if "summary_tool" in available_tools and memory.get("route"):
                shop = memory.get("shop") if isinstance(memory.get("shop"), dict) else {}
                return self._single_tool_call(
                    name="summary_tool",
                    arguments={
                        "topic": "navigation",
                        "keyword": None,
                        "total": None,
                        "shops": None,
                        "shop_name": shop.get("name") or "target arcade",
                        "route": memory.get("route"),
                    },
                )

            return ModelResponse(
                text="navigation requires `shop_id`; select a destination and retry.",
                tool_calls=[],
                reasoning_items=[],
            )

        if active_subagent == "summary_agent":
            existing_reply = memory.get("reply")
            if isinstance(existing_reply, str) and existing_reply.strip():
                return ModelResponse(text=existing_reply.strip(), tool_calls=[], reasoning_items=[])
            if "summary_tool" in available_tools:
                if intent == "navigate":
                    shop = memory.get("shop") if isinstance(memory.get("shop"), dict) else {}
                    return self._single_tool_call(
                        name="summary_tool",
                        arguments={
                            "topic": "navigation",
                            "keyword": None,
                            "total": None,
                            "shops": None,
                            "shop_name": shop.get("name") or "target arcade",
                            "route": memory.get("route"),
                        },
                    )
                return self._single_tool_call(
                    name="summary_tool",
                    arguments={
                        "topic": "search",
                        "keyword": memory.get("keyword"),
                        "total": memory.get("total"),
                        "shops": memory.get("shops"),
                        "shop_name": None,
                        "route": None,
                    },
                )

        return ModelResponse(text=None, tool_calls=[], reasoning_items=[])

    def _single_tool_call(self, *, name: str, arguments: dict[str, Any]) -> ModelResponse:
        return ModelResponse(
            text=None,
            tool_calls=[
                ModelToolCall(
                    call_id=f"offline_{uuid4().hex[:12]}",
                    name=name,
                    arguments=arguments,
                )
            ],
            reasoning_items=[],
        )

    def _tool_name_set(self, tools: list[dict[str, Any]]) -> set[str]:
        names: set[str] = set()
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            function_obj = tool.get("function")
            if isinstance(function_obj, dict):
                name = function_obj.get("name")
                if isinstance(name, str) and name:
                    names.add(name)
        return names
