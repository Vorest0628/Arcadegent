"""Tool layer: natural-language summarizer for search/navigation responses."""

from __future__ import annotations

from app.infra.llm.openai_compatible_client import OpenAICompatibleClient
from app.protocol.messages import RouteSummaryDto


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

    def summarize_search(self, keyword: str | None, total: int, shops: list[dict]) -> str:
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
                "Return a concise Chinese summary in under 120 Chinese characters."
            ),
            user_prompt=str(llm_prompt),
        )
        if llm_result:
            return llm_result

        if total <= 0:
            if keyword:
                return f"No arcades found for '{keyword}'. Try another keyword or location filter."
            return "No arcades found for current filters."

        preview = [
            f"{idx}. {row.get('name')} ({row.get('city_name') or 'unknown city'})"
            for idx, row in enumerate(shops[:3], start=1)
        ]
        prefix = f"Found {total} arcade locations."
        return prefix + (" Suggested first: " + "; ".join(preview) if preview else "")

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
