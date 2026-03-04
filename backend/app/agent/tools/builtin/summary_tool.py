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

    def _is_unreliable_search_reply(
        self,
        reply: str,
        *,
        total: int,
        sort_by: str | None = None,
        sort_title_name: str | None = None,
    ) -> bool:
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

        if bool(
            re.search(
                r"(\u6682\u65e0|\u672a\u627e\u5230|\u672a\u67e5\u5230).*(\u6570\u636e|\u5e97\u94fa|\u673a\u5385)",
                text,
            )
        ):
            return True

        if (sort_by or "").strip().lower() == "title_quantity" and sort_title_name:
            # total here means number of shops, not number of machines.
            if re.search(rf"\b{total}\s*(\u53f0|machines?)\b", text):
                return True

        return False

    @staticmethod
    def _normalize_title_name(value: str | None) -> str:
        if not value:
            return ""
        text = str(value).strip().lower()
        text = re.sub(r"[\s_\-./]+", "", text)
        if "\u821e\u840c" in text or text.startswith("maimai"):
            return "maimai"
        if text.startswith("soundvoltex") or text == "sdvx":
            return "sdvx"
        return text

    def _title_quantity(self, row: dict, title_name: str) -> int:
        needle = self._normalize_title_name(title_name)
        if not needle:
            return 0

        total = 0
        for item in row.get("arcades") or []:
            if not isinstance(item, dict):
                continue
            raw_name = self._normalize_title_name(item.get("title_name"))
            if raw_name != needle:
                continue
            try:
                total += int(item.get("quantity") or 0)
            except (TypeError, ValueError):
                continue
        return total

    def _deterministic_title_quantity_summary(
        self,
        *,
        total: int,
        shops: list[dict],
        sort_order: str | None,
        sort_title_name: str,
    ) -> str:
        title = sort_title_name.strip()
        order = (
            "\u7531\u9ad8\u5230\u4f4e"
            if (sort_order or "desc").strip().lower() != "asc"
            else "\u7531\u4f4e\u5230\u9ad8"
        )

        preview_parts: list[str] = []
        for idx, row in enumerate(shops[:5], start=1):
            qty = self._title_quantity(row, title)
            name = str(row.get("name") or "unknown arcade")
            city = str(row.get("city_name") or "-")
            preview_parts.append(f"{idx}. {name}({city}) {qty}\u53f0")

        prefix = (
            f"\u5171\u627e\u5230 {total} \u5bb6\u673a\u5385\uff0c"
            f"\u6309 {title} \u673a\u53f0\u6570{order}\u6392\u5e8f\u3002"
        )
        if not preview_parts:
            return prefix
        return f"{prefix} \u5f53\u524d\u9875\u524d{len(preview_parts)}\uff1a{'\uff1b'.join(preview_parts)}\u3002"

    def summarize_search(
        self,
        keyword: str | None,
        total: int,
        shops: list[dict],
        *,
        sort_by: str | None = None,
        sort_order: str | None = None,
        sort_title_name: str | None = None,
    ) -> str:
        logger.info(
            "summary_tool.search keyword=%s total=%s shops=%s sort_by=%s sort_order=%s sort_title_name=%s",
            " ".join((keyword or "").split())[:64],
            total,
            len(shops),
            sort_by,
            sort_order,
            (sort_title_name or "").strip()[:64],
        )

        if (
            total > 0
            and (sort_by or "").strip().lower() == "title_quantity"
            and isinstance(sort_title_name, str)
            and sort_title_name.strip()
        ):
            return self._deterministic_title_quantity_summary(
                total=total,
                shops=shops,
                sort_order=sort_order,
                sort_title_name=sort_title_name,
            )

        llm_prompt = {
            "keyword": keyword,
            "total": total,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "sort_title_name": sort_title_name,
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
                "If total > 0, never claim no data or not found. "
                "The total value means number of shops, not number of machines."
            ),
            user_prompt=str(llm_prompt),
        )
        if llm_result and not self._is_unreliable_search_reply(
            llm_result,
            total=total,
            sort_by=sort_by,
            sort_title_name=sort_title_name,
        ):
            return llm_result

        if total <= 0:
            if keyword:
                return (
                    f"\u672a\u627e\u5230\u5339\u914d\u2018{keyword}\u2019\u7684\u673a\u5385\uff0c"
                    "\u8bf7\u5c1d\u8bd5\u5176\u4ed6\u5173\u952e\u8bcd\u6216\u533a\u57df\u3002"
                )
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
