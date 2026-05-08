"""测试 AgentLoop.arun() 异步接口和回调机制."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from course_agent.core import AgentLoop
from course_agent.llm import MockLLM


class RecordingCallbacks:
    """记录所有回调事件的假实现."""

    def __init__(self) -> None:
        self.events: list[tuple[str, tuple]] = []

    async def on_thought(self, step: int, content: str) -> None:
        self.events.append(("thought", (step, content)))

    async def on_tool_call(self, step: int, name: str, args: dict[str, Any]) -> None:
        self.events.append(("tool_call", (step, name, args)))

    async def on_tool_result(
        self, step: int, name: str, result: str, is_error: bool = False
    ) -> None:
        self.events.append(("tool_result", (step, name, result, is_error)))

    async def on_final(self, answer: str) -> None:
        self.events.append(("final", (answer,)))


def test_arun_math_with_callbacks():
    loop = AgentLoop(llm=MockLLM(), max_steps=5)
    cb = RecordingCallbacks()

    result = asyncio.run(loop.arun("帮我算一下 (3+5)*2 等于多少", callbacks=cb))

    assert result.steps >= 1
    assert "16" in result.answer

    kinds = [e[0] for e in cb.events]
    assert "tool_call" in kinds
    assert "tool_result" in kinds
    assert kinds[-1] == "final"


def test_arun_without_callbacks():
    """不传 callbacks 应像 run() 一样正常工作."""
    loop = AgentLoop(llm=MockLLM(), max_steps=3)
    result = asyncio.run(loop.arun("你好"))
    assert result.answer
    assert result.steps >= 1


def test_arun_direct_answer():
    loop = AgentLoop(llm=MockLLM(), max_steps=3)
    cb = RecordingCallbacks()
    result = asyncio.run(loop.arun("做个自我介绍", callbacks=cb))

    assert result.answer
    kinds = [e[0] for e in cb.events]
    assert "final" in kinds


def test_arun_with_history():
    """传入多轮历史应能保留上下文."""
    from course_agent.llm.base import LLMMessage

    loop = AgentLoop(llm=MockLLM(), max_steps=3)
    history = [
        LLMMessage(role="system", content="你是助手"),
        LLMMessage(role="user", content="之前问过的问题"),
        LLMMessage(role="assistant", content="之前的回答"),
    ]
    result = asyncio.run(
        loop.arun("接着上面的继续", history=history, callbacks=None)
    )
    assert result.answer
    assert result.steps >= 1


def test_arun_respects_max_steps():
    loop = AgentLoop(llm=MockLLM(), max_steps=1)
    result = asyncio.run(loop.arun("帮我算 1+2+3"))
    assert result.steps <= 1


@pytest.mark.asyncio
async def test_callbacks_exception_does_not_break_loop():
    """回调异常不应中断主流程."""

    class BrokenCallbacks:
        async def on_tool_call(self, *args, **kwargs):
            raise RuntimeError("callback boom")

        async def on_final(self, answer):
            pass

    loop = AgentLoop(llm=MockLLM(), max_steps=5)
    result = await loop.arun("帮我算 (3+5)*2", callbacks=BrokenCallbacks())
    assert "16" in result.answer
