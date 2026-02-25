"""Provider adapter with Responses/Chat Completions dual-stack fallback."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib import error, request
from uuid import uuid4

from app.agent.llm.llm_config import LLMConfig


def _safe_json_loads(raw: str | bytes | None) -> dict[str, Any]:
    if raw is None:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


@dataclass(frozen=True)
class ModelToolCall:
    """Normalized function call emitted by provider model."""

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
        # Keep arg for compatibility with caller signature.
        _ = runtime_hints

        if not self.enabled:
            return self._error_response("llm provider disabled: missing api key")

        by_responses, responses_error = self._try_responses_api(
            instructions=instructions,
            messages=messages,
            tools=tools,
        )
        if by_responses is not None:
            return by_responses

        by_chat, chat_error = self._try_chat_completions(
            instructions=instructions,
            messages=messages,
            tools=tools,
        )
        if by_chat is not None:
            return by_chat

        return self._error_response(
            "llm provider failed after trying responses and chat completions; "
            f"responses_error={self._format_error(responses_error)}; "
            f"chat_completions_error={self._format_error(chat_error)}"
        )

    def _post_json(
        self,
        *,
        endpoint: str,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str | None]:
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
                decoded = _safe_json_loads(resp.read().decode("utf-8", errors="replace"))
                if not isinstance(decoded, dict):
                    return None, "response body is not a JSON object"
                return decoded, None
        except error.HTTPError as exc:
            details = ""
            try:
                raw = exc.read()
                if raw:
                    details = " ".join(raw.decode("utf-8", errors="replace").split())
            except Exception:
                details = ""
            suffix = f"; body={details[:280]}" if details else ""
            return None, f"http_error status={exc.code} reason={exc.reason}{suffix}"
        except error.URLError as exc:
            return None, f"url_error reason={exc.reason}"
        except TimeoutError:
            return None, "timeout_error request timed out"
        except Exception as exc:  # pragma: no cover
            return None, f"unexpected_error {type(exc).__name__}: {exc}"

    def _try_responses_api(
        self,
        *,
        instructions: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> tuple[ModelResponse | None, str | None]:
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

        decoded, request_error = self._post_json(endpoint=endpoint, payload=payload)
        if not isinstance(decoded, dict):
            return None, request_error or "responses api returned no data"

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
            return None, "responses api returned no text, tool_calls, or reasoning"

        response_id = decoded.get("id")
        return (
            ModelResponse(
                text=text,
                tool_calls=tool_calls,
                reasoning_items=reasoning,
                response_id=str(response_id) if response_id is not None else None,
            ),
            None,
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
    ) -> tuple[ModelResponse | None, str | None]:
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

        decoded, request_error = self._post_json(endpoint=endpoint, payload=payload)
        if not isinstance(decoded, dict):
            return None, request_error or "chat completions api returned no data"

        choices = decoded.get("choices")
        if not isinstance(choices, list) or not choices:
            return None, "chat completions api returned empty choices"

        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first, dict) else None
        if not isinstance(message, dict):
            return None, "chat completions api returned invalid message payload"

        text = self._extract_chat_text(message.get("content"))
        tool_calls: list[ModelToolCall] = []
        raw_tool_calls = message.get("tool_calls")
        if isinstance(raw_tool_calls, list):
            for raw_call in raw_tool_calls:
                parsed = self._parse_chat_tool_call(raw_call)
                if parsed:
                    tool_calls.append(parsed)

        if text is None and not tool_calls:
            return None, "chat completions api returned no text or tool_calls"
        return ModelResponse(text=text, tool_calls=tool_calls, reasoning_items=[]), None

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

    def _error_response(self, message: str) -> ModelResponse:
        return ModelResponse(text=f"error: {message}", tool_calls=[], reasoning_items=[])

    def _format_error(self, value: str | None) -> str:
        if not value:
            return "unknown"
        compact = " ".join(value.split())
        if len(compact) <= 280:
            return compact
        return compact[:277] + "..."
