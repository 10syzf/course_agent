"""Agent 运行态数据结构."""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from course_agent.llm.base import LLMMessage


class TraceEntry(BaseModel):
    """Agent Loop 单步 trace."""

    step: int
    kind: Literal["think", "tool_call", "tool_result", "final"]
    content: str
    data: dict[str, Any] | None = None


class AgentState(BaseModel):
    """Agent 运行时状态."""

    messages: list[LLMMessage] = Field(default_factory=list)
    scratchpad: list[str] = Field(default_factory=list)
    trace: list[TraceEntry] = Field(default_factory=list)
    step: int = 0
    done: bool = False
    final_answer: str | None = None

    def add_message(self, message: LLMMessage) -> None:
        self.messages.append(message)

    def add_trace(
        self,
        kind: Literal["think", "tool_call", "tool_result", "final"],
        content: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.trace.append(TraceEntry(step=self.step, kind=kind, content=content, data=data))


@runtime_checkable
class AgentCallbacks(Protocol):
    """Agent Loop 回调接口，供 UI 层订阅事件.

    所有方法都是异步的；UI 适配器（如 Chainlit）实现这些方法以把事件翻译成界面更新。
    实现是 optional 的——每个方法都有默认实现，未实现的回调会被跳过。
    """

    async def on_thought(self, step: int, content: str) -> None:  # noqa: D401
        """LLM 产出思考内容（可能伴随 tool_calls）."""
        ...

    async def on_tool_call(self, step: int, name: str, args: dict[str, Any]) -> None:
        """Agent 即将执行工具调用."""
        ...

    async def on_tool_result(
        self, step: int, name: str, result: str, is_error: bool = False
    ) -> None:
        """工具执行完成，返回结果."""
        ...

    async def on_final(self, answer: str) -> None:
        """Agent 产出最终答案."""
        ...

