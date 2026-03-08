"""Context assembly for ReAct runtime turns."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.agent.runtime.session_state import AgentSessionState, AgentTurn
from app.agent.subagents.subagent_builder import SubAgentProfile
from app.protocol.messages import ChatRequest


@dataclass(frozen=True)
class BuiltContext:
    """Prepared prompt payload for provider adapter."""

    instructions: str
    messages: list[dict[str, Any]]


class ContextBuilder:
    """Build model instructions and messages from session history."""

    def __init__(
        self,
        *,
        prompt_root: Path,
        history_turn_limit: int,
        skill_root: Path | None = None,
    ) -> None:
        self._prompt_root = prompt_root
        self._skill_root = skill_root
        self._history_turn_limit = max(4, history_turn_limit)
        self._prompt_cache: dict[str, str] = {}
        self._skill_cache: dict[str, str] = {}

    def build(
        self,
        *,
        session_state: AgentSessionState,
        request: ChatRequest,
        subagent: SubAgentProfile,
    ) -> BuiltContext:
        base_prompt = self._load_prompt("system_base.md").strip()
        subagent_prompt = self._load_prompt(subagent.prompt_file).strip()
        skill_block = self._build_skill_block(subagent.skill_files)
        runtime_hint = {
            "session_id": session_state.session_id,
            "turn_index": session_state.turn_index,
            "active_subagent": session_state.active_subagent,
            "intent": session_state.intent,
            "request": request.model_dump(mode="json"),
            "memory_summary": {
                "has_shops": bool(session_state.working_memory.get("shops")),
                "has_route": bool(session_state.working_memory.get("route")),
            },
            "memory_snapshot": self._memory_snapshot(session_state),
        }

        instruction_parts = [base_prompt]
        if skill_block:
            instruction_parts.append(skill_block)
        instruction_parts.extend(
            (
                subagent_prompt,
                "Runtime state (JSON):",
                json.dumps(runtime_hint, ensure_ascii=False),
            )
        )
        instructions = "\n\n".join(part for part in instruction_parts if part)
        messages = [self._to_model_message(turn) for turn in self._tail_turns(session_state.turns)]
        return BuiltContext(instructions=instructions, messages=messages)

    def _tail_turns(self, turns: list[AgentTurn]) -> list[AgentTurn]:
        if len(turns) <= self._history_turn_limit:
            return turns
        return turns[-self._history_turn_limit :]

    def _to_model_message(self, turn: AgentTurn) -> dict[str, Any]:
        if turn.role == "tool":
            payload: dict[str, Any] = {
                "role": "tool",
                "content": turn.content,
            }
            if turn.name:
                payload["name"] = turn.name
            if turn.call_id:
                payload["tool_call_id"] = turn.call_id
            return payload
        return {"role": turn.role, "content": turn.content}

    def _build_skill_block(self, skill_files: list[str]) -> str:
        sections: list[str] = []
        for filename in skill_files:
            content = self._load_skill(filename).strip()
            if not content:
                continue
            sections.append(f"Skill reference: {filename}\n{content}")
        if not sections:
            return ""
        return "\n\n".join(sections)

    def _memory_snapshot(self, session_state: AgentSessionState) -> dict[str, Any]:
        memory = session_state.working_memory
        snapshot: dict[str, Any] = {}

        for key in ("keyword", "total", "provider", "last_shop_id"):
            value = memory.get(key)
            if value is not None and value != "":
                snapshot[key] = value

        last_db_query = memory.get("last_db_query")
        if isinstance(last_db_query, dict):
            snapshot["last_db_query"] = self._compact_dict(last_db_query)

        shop = memory.get("shop")
        if isinstance(shop, dict):
            snapshot["shop"] = self._shop_snapshot(shop)

        shops = memory.get("shops")
        if isinstance(shops, list):
            shop_dicts = [item for item in shops if isinstance(item, dict)]
            if shop_dicts:
                snapshot["shops_count"] = len(shop_dicts)
                snapshot["shops_preview"] = [self._shop_snapshot(item) for item in shop_dicts[:5]]

        route = memory.get("route")
        if isinstance(route, dict):
            snapshot["route"] = self._compact_dict(
                {
                    "provider": route.get("provider"),
                    "mode": route.get("mode"),
                    "distance_m": route.get("distance_m"),
                    "duration_s": route.get("duration_s"),
                    "hint": route.get("hint"),
                }
            )
        return snapshot

    def _shop_snapshot(self, raw: dict[str, Any]) -> dict[str, Any]:
        arcades_preview: list[dict[str, Any]] = []
        for item in raw.get("arcades") or []:
            if not isinstance(item, dict):
                continue
            arcades_preview.append(
                self._compact_dict(
                    {
                        "title_name": item.get("title_name"),
                        "quantity": item.get("quantity"),
                    }
                )
            )
            if len(arcades_preview) >= 12:
                break

        payload = self._compact_dict(
            {
                "source_id": raw.get("source_id"),
                "name": raw.get("name"),
                "province_name": raw.get("province_name"),
                "city_name": raw.get("city_name"),
                "county_name": raw.get("county_name"),
                "address": raw.get("address"),
                "arcade_count": raw.get("arcade_count"),
            }
        )
        if arcades_preview:
            payload["arcades"] = arcades_preview
        return payload

    def _compact_dict(self, raw: dict[str, Any]) -> dict[str, Any]:
        compact: dict[str, Any] = {}
        for key, value in raw.items():
            if value is None or value == "":
                continue
            compact[str(key)] = value
        return compact

    def _load_prompt(self, filename: str) -> str:
        return self._load_markdown(
            filename=filename,
            root=self._prompt_root,
            cache=self._prompt_cache,
        )

    def _load_skill(self, filename: str) -> str:
        if self._skill_root is None:
            return ""
        return self._load_markdown(
            filename=filename,
            root=self._skill_root,
            cache=self._skill_cache,
        )

    def _load_markdown(
        self,
        *,
        filename: str,
        root: Path,
        cache: dict[str, str],
    ) -> str:
        if filename in cache:
            return cache[filename]
        path = root / filename
        if not path.exists():
            content = ""
        else:
            content = path.read_text(encoding="utf-8")
        cache[filename] = content
        return content
