"""Unit tests for search summary robustness behavior."""

from __future__ import annotations

from app.agent.tools.builtin.summary_tool import SummaryTool


class _StubLLM:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    def chat_completion(self, *, system_prompt: str, user_prompt: str) -> str | None:
        _ = system_prompt
        _ = user_prompt
        return self._reply


def test_summary_tool_ignores_unreliable_llm_reply_when_results_exist() -> None:
    tool = SummaryTool(llm_client=_StubLLM("\u62b1\u6b49\uff0c\u6211\u65e0\u6cd5\u76f4\u63a5\u67e5\u8be2\u8be5\u5730\u533a\u6570\u636e\u3002"))  # type: ignore[arg-type]
    text = tool.summarize_search(
        keyword="maimai",
        total=3,
        shops=[
            {"name": "A", "city_name": "Shanghai"},
            {"name": "B", "city_name": "Shanghai"},
        ],
    )
    assert "\u5171\u627e\u5230 3 \u5bb6\u673a\u5385\u3002" in text


def test_summary_tool_ignores_no_data_reply_when_results_exist() -> None:
    tool = SummaryTool(llm_client=_StubLLM("\u5f53\u524d\u6682\u65e0\u76f8\u5173\u5e97\u94fa\u6570\u636e\uff0c\u8bf7\u5c1d\u8bd5\u5176\u4ed6\u6761\u4ef6\u3002"))  # type: ignore[arg-type]
    text = tool.summarize_search(
        keyword="\u9ec4\u6d66\u533a",
        total=5,
        shops=[{"name": "X", "city_name": "Shanghai"}],
    )
    assert "\u5171\u627e\u5230 5 \u5bb6\u673a\u5385\u3002" in text


def test_summary_tool_keeps_llm_reply_when_no_results() -> None:
    tool = SummaryTool(llm_client=_StubLLM("\u62b1\u6b49\uff0c\u672a\u67e5\u5230\u7b26\u5408\u6761\u4ef6\u7684\u673a\u5385\u3002"))  # type: ignore[arg-type]
    text = tool.summarize_search(
        keyword="unknown",
        total=0,
        shops=[],
    )
    assert text == "\u62b1\u6b49\uff0c\u672a\u67e5\u5230\u7b26\u5408\u6761\u4ef6\u7684\u673a\u5385\u3002"
