"""Tool layer: natural-language summarizer for search/navigation responses."""

from __future__ import annotations

import re

from app.infra.llm.openai_compatible_client import OpenAICompatibleClient
from app.infra.observability.logger import get_logger
from app.protocol.messages import RouteSummaryDto

logger = get_logger(__name__)


class SummaryTool:
    """Template-based response summarizer used by orchestration runtime."""

    def __init__(self, llm_client: OpenAICompatibleClient | None = None) -> None:
        self._llm_client = llm_client

    def _call_llm(self, *, system_prompt: str, user_prompt: str) -> str | None:
        if not self._llm_client:
            return None
        return self._llm_client.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    def _is_unreliable_search_reply(self, reply: str, *, total: int) -> bool:
        text = " ".join(reply.split()).lower()
        if total <= 0:
            return False
        red_flags = (
            "\u65e0\u6cd5",
            "\u4e0d\u80fd",
            "\u62b1\u6b49",
            "\u6682\u65e0",
            "\u65e0\u76f8\u5173",
            "\u6ca1\u6709\u76f8\u5173",
            "\u672a\u627e\u5230",
            "\u672a\u67e5\u5230",
            "no access",
            "can't access",
            "not found",
            "no result",
        )
        if any(flag in text for flag in red_flags):
            return True
        return bool(
            re.search(
                r"(\u6682\u65e0|\u672a\u627e\u5230|\u672a\u67e5\u5230).*(\u6570\u636e|\u5e97\u94fa|\u673a\u5385)",
                text,
            )
        )

    def summarize_search(self, keyword: str | None, total: int, shops: list[dict]) -> str:
        logger.info(
            "summary_tool.search keyword=%s total=%s shops=%s",
            " ".join((keyword or "").split())[:64],
            total,
            len(shops),
        )

        llm_prompt = {
            "keyword": keyword,
            "total": total,
            "top_shops": [
                {
                    "name": row.get("name"),
                    "city_name": row.get("city_name"),
                    "county_name": row.get("county_name"),
                    "arcade_count": row.get("arcade_count"),
                }
                for row in shops[:5]
            ],
        }
        llm_result = self._call_llm(
            system_prompt=(
                "You are Arcadegent search assistant. "
                "Return a concise Chinese summary in under 120 Chinese characters. "
                "If total > 0, never claim no data or not found."
            ),
            user_prompt=str(llm_prompt),
        )
        if llm_result and not self._is_unreliable_search_reply(llm_result, total=total):
            return llm_result

        if total <= 0:
            if keyword:
                return f"\u672a\u627e\u5230\u5339\u914d\u2018{keyword}\u2019\u7684\u673a\u5385\uff0c\u8bf7\u5c1d\u8bd5\u5176\u4ed6\u5173\u952e\u8bcd\u6216\u533a\u57df\u3002"
            return "\u672a\u627e\u5230\u7b26\u5408\u6761\u4ef6\u7684\u673a\u5385\u3002"

        preview = [
            f"{idx}. {row.get('name') or 'unknown arcade'} ({row.get('city_name') or 'unknown city'})"
            for idx, row in enumerate(shops[:3], start=1)
        ]
        prefix = f"\u5171\u627e\u5230 {total} \u5bb6\u673a\u5385\u3002"
        return prefix + (f" \u53ef\u4f18\u5148\u53c2\u8003\uff1a{'; '.join(preview)}" if preview else "")

    def summarize_navigation(self, shop_name: str, route: RouteSummaryDto) -> str:
        llm_result = self._call_llm(
            system_prompt=(
                "You are Arcadegent navigation assistant. "
                "Return a concise Chinese route summary under 100 Chinese characters."
            ),
            user_prompt=str(
                {
                    "shop_name": shop_name,
                    "provider": route.provider,
                    "mode": route.mode,
                    "distance_m": route.distance_m,
                    "duration_s": route.duration_s,
                    "hint": route.hint,
                }
            ),
        )
        if llm_result:
            return llm_result

        dist = route.distance_m if route.distance_m is not None else 0
        mins = int((route.duration_s or 0) / 60)
        return f"Route to {shop_name} ({route.mode}): {dist} meters, about {mins} minutes."
