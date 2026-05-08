"""LLM 抽象基类和数据结构."""

from __future__ import annotations

from abc import ABC, abstractmethod
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
