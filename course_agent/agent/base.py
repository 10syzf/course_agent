"""Agent 抽象层（Task 012）.

把 Task 011 的 ExaminerAgent 范式（限定工具集 + 独立 system_prompt + 复用 AgentLoop）
抽象成两个共享原件：

- ``BaseAgent``：Protocol 而非 ABC——让 ``ExaminerAgent`` 0 改动天然满足契约；
  PlannerAgent / SolverAgent / CriticAgent / Orchestrator 全部按这个模板套出。
- ``AgentMessage``：跨 Agent 传递的结构化消息（带 ``agent_name`` 来源标识 + ``meta`` 自由扩展）。

设计要点：
- 4 个 Agent 都暴露 ``arun()`` + ``astream_run()`` 两套接口（与 AgentLoop 对齐）
- 测试只跑 ``arun()`` 即可，流式留给 UI 层
- ``allowed_tools`` 是 Agent 的"身份证"：白名单收紧后 schema 里都没有，LLM 想犯错都没机会
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from course_agent.core.state import AgentCallbacks
from course_agent.llm.base import LLMMessage, StreamChunk


class AgentMessage(BaseModel):
    """多 Agent 之间传递的结构化消息.

    与 ``LLMMessage`` 的区别：``LLMMessage`` 是给 LLM 看的（OpenAI 协议格式），
    ``AgentMessage`` 是给 Orchestrator 看的（含 ``agent_name`` 来源 + ``meta`` 自由扩展）。
    """

    agent_name: str
    role: str = "assistant"
    content: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)

    def to_llm_message(self) -> LLMMessage:
        """把 AgentMessage 转成可塞进 LLM history 的 LLMMessage."""
        prefix = f"[{self.agent_name}] " if self.agent_name else ""
        role = self.role if self.role in ("system", "user", "assistant", "tool") else "assistant"
        return LLMMessage(role=role, content=prefix + self.content)


@runtime_checkable
class BaseAgent(Protocol):
    """所有专职 Agent 的契约：必须暴露名字 + 工具白名单 + arun + astream_run.

    用 ``Protocol`` 而非 ``ABC``，目的是让 Task 011 的 ``ExaminerAgent``（已存在）
    无需改继承结构就天然满足契约——只要鸭子类型对得上就行。
    """

    name: str
    allowed_tools: list[str]

    async def arun(
        self,
        user_input: str,
        history: list[LLMMessage] | None = None,
        callbacks: AgentCallbacks | None = None,
    ) -> Any:
        ...

    def astream_run(
        self,
        user_input: str,
        history: list[LLMMessage] | None = None,
        callbacks: AgentCallbacks | None = None,
    ) -> AsyncIterator[StreamChunk]:
        ...


__all__ = ["AgentMessage", "BaseAgent"]
