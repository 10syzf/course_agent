"""MockLLM：基于规则匹配的假模型，用于本地跑通 Agent Loop."""

from __future__ import annotations

import re
import uuid
from typing import Any

from course_agent.llm.base import BaseLLM, LLMMessage, LLMResponse, ToolCall


class MockLLM(BaseLLM):
    """规则驱动的 Mock LLM：根据用户输入决定是否调用工具.

    规则（按优先级从上到下匹配）：
      1. 数学表达式  -> 调用 calculator
      2. "搜索/search" -> 调用 web_search
      3. "读取文件"   -> 调用 file_read
      4. "写入文件"   -> 调用 file_write
      5. 其它        -> 直接回答
    """

    def __init__(self, model: str = "mock-llm", **kwargs: Any) -> None:
        super().__init__(model=model, **kwargs)

    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        last_user = next(
            (m for m in reversed(messages) if m.role == "user"),
            None,
        )
        last_tool = next(
            (m for m in reversed(messages) if m.role == "tool"),
            None,
        )
        user_text = (last_user.content if last_user else "") or ""

        if last_tool is not None:
            return LLMResponse(
                content=f"根据工具返回的结果：{last_tool.content}\n这是最终回答。",
                finish_reason="stop",
            )

        tool_names = {t["function"]["name"] for t in (tools or [])}

        math_match = re.search(r"([\d\.\+\-\*\/\(\)\s]+)", user_text)
        if math_match and re.search(r"[\+\-\*\/]", math_match.group(1)):
            if "calculator" in tool_names:
                return self._tool_call("calculator", {"expression": math_match.group(1).strip()})

        if any(k in user_text for k in ["搜索", "search", "查一下", "查查"]):
            if "web_search" in tool_names:
                return self._tool_call("web_search", {"query": user_text})

        if "读取文件" in user_text or "read file" in user_text.lower():
            path_match = re.search(r"[:\s]([\w\./\-]+\.\w+)", user_text)
            if "file_read" in tool_names and path_match:
                return self._tool_call("file_read", {"path": path_match.group(1)})

        if "写入文件" in user_text or "write file" in user_text.lower():
            if "file_write" in tool_names:
                return self._tool_call(
                    "file_write",
                    {"path": "output.txt", "content": user_text},
                )

        return LLMResponse(
            content=(
                f"[MockLLM] 我收到了你的问题：\"{user_text}\"。"
                f"当前没有合适的工具可用或无需调用工具，这是一个占位回答。"
            ),
            finish_reason="stop",
        )

    @staticmethod
    def _tool_call(name: str, arguments: dict[str, Any]) -> LLMResponse:
        return LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(id=f"call_{uuid.uuid4().hex[:8]}", name=name, arguments=arguments)
            ],
            finish_reason="tool_calls",
        )
