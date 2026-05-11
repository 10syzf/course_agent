"""LLM 抽象基类和数据结构."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]


class LLMMessage(BaseModel):
    """统一的消息格式，兼容 OpenAI 风格."""

    role: Role
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] | None = None

    def to_openai(self) -> dict[str, Any]:
        data: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            data["content"] = self.content
        if self.name:
            data["name"] = self.name
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            data["tool_calls"] = [tc.to_openai() for tc in self.tool_calls]
        return data


class ToolCall(BaseModel):
    """工具调用请求."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)

    def to_openai(self) -> dict[str, Any]:
        import json

        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments, ensure_ascii=False),
            },
        }


class LLMResponse(BaseModel):
    """LLM 返回结果."""

    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str = "stop"
    raw: dict[str, Any] | None = None


class StreamChunk(BaseModel):
    """流式片段（Task 011）.

    一次 ``astream()`` 迭代抛出一个 chunk，可能包含：
      - delta_text：文本增量（直接外抛给 UI 打字机）
      - tool_call_delta：tool_call 拼装中的增量（内部拼到完整再执行）
      - finish_reason：'stop' / 'tool_calls' / 'length' / 'error' / None

    设计原则：尽量贴 OpenAI streaming chunk 的 shape，便于 provider 直转。
    """

    delta_text: str = ""
    tool_call_delta: dict[str, Any] | None = None
    finish_reason: str | None = None
    error: str | None = None


LLMMessage.model_rebuild()


class BaseLLM(ABC):
    """LLM 抽象基类：所有具体 provider 都需实现 chat."""

    def __init__(self, model: str, **kwargs: Any) -> None:
        self.model = model
        self.kwargs = kwargs

    @abstractmethod
    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """发起一次同步 chat 请求."""
        raise NotImplementedError

    async def achat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """异步版本的 chat.

        默认实现：用线程池包装同步 chat，避免阻塞事件循环。
        具体 provider（如 OpenAI）可以覆盖为真正的异步实现以获得更好性能。
        """
        import asyncio

        return await asyncio.to_thread(self.chat, messages, tools, **kwargs)

    async def astream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """流式 chat（Task 011）.

        默认实现：先调一遍 ``achat()`` 把整段 content 拿到，再按字符切成假流式。
        provider 应当覆盖为真正的 ``stream=True`` 调用以获得真正的打字机效果。

        约定：
        - 文本 chunk 通过 ``delta_text`` 外抛
        - tool_call 整体作为 ``tool_call_delta`` 一次性给出（默认实现下没法逐 token）
        - 最后一个 chunk 的 ``finish_reason`` 必须非 None
        - 出错时 yield 一条 ``finish_reason='error'`` + ``error`` 字段
        """
        try:
            resp = await self.achat(messages, tools=tools, **kwargs)
        except Exception as e:  # noqa: BLE001
            yield StreamChunk(finish_reason="error", error=f"{type(e).__name__}: {e}")
            return

        text = resp.content or ""
        # 按 4 字符一片做"假流式"，便于上层单测 + UI 体感
        step = 4
        for i in range(0, len(text), step):
            yield StreamChunk(delta_text=text[i : i + step])

        for tc in resp.tool_calls:
            import json as _json

            yield StreamChunk(
                tool_call_delta={
                    "index": 0,
                    "id": tc.id,
                    "function": {
                        "name": tc.name,
                        "arguments": _json.dumps(tc.arguments, ensure_ascii=False),
                    },
                },
            )

        yield StreamChunk(finish_reason=resp.finish_reason or "stop")
