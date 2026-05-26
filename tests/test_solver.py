"""SolverAgent 单测（Task 012）.

覆盖：
- _build_sub_task_prompt 拼装含 id / title / expected_output / suggested_tools
- 全工具集（registry 中所有 names 都在 allowed_tools）
- arun 返回 AgentResult（answer/steps/trace）
- solve() 接收 sub_task dict 并直接调底层 loop
- system_prompt 包含 Solver 关键词
- history 透传不抛错
"""

from __future__ import annotations

from typing import Any

import pytest

from course_agent.agent import SolverAgent
from course_agent.agent.solver import (
    SOLVER_SYSTEM_PROMPT,
    _build_sub_task_prompt,
)
from course_agent.llm.base import BaseLLM, LLMMessage, LLMResponse
from course_agent.llm.mock import MockLLM
from course_agent.tools.registry import Tool, ToolRegistry


class _OneShotLLM(BaseLLM):
    def __init__(self, text: str = "好的，结论：42") -> None:
        super().__init__(model="oneshot-solver")
        self._text = text

    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        return LLMResponse(content=self._text, finish_reason="stop")


def _make_registry(n: int = 3) -> ToolRegistry:
    reg = ToolRegistry()
    for i in range(n):
        reg.register(
            Tool(
                name=f"tool_{i}",
                description=f"stub {i}",
                parameters={"type": "object", "properties": {}, "required": []},
                func=lambda **_: "ok",
            )
        )
    return reg


def test_build_sub_task_prompt_contains_all_fields():
    st = {
        "id": 7,
        "title": "求 1+1",
        "expected_output": "返回结果 2",
        "suggested_tools": ["calculator"],
    }
    p = _build_sub_task_prompt(st)
    assert "#7" in p
    assert "求 1+1" in p
    assert "返回结果 2" in p
    assert "calculator" in p


def test_build_sub_task_prompt_handles_missing_suggested_tools():
    st = {"id": 1, "title": "t", "expected_output": "o"}
    p = _build_sub_task_prompt(st)
    assert "无建议" in p or "自行选择" in p


def test_solver_uses_full_tool_set():
    reg = _make_registry(5)
    s = SolverAgent(llm=MockLLM(), registry=reg)
    assert sorted(s.allowed_tools) == sorted([f"tool_{i}" for i in range(5)])


def test_solver_system_prompt_keywords():
    assert "Solver" in SOLVER_SYSTEM_PROMPT
    assert "expected_output" in SOLVER_SYSTEM_PROMPT


def test_solver_repr_shows_tool_count():
    reg = _make_registry(4)
    s = SolverAgent(llm=MockLLM(), registry=reg, max_steps=5)
    r = repr(s)
    assert "SolverAgent" in r
    assert "4" in r
    assert "max_steps=5" in r


@pytest.mark.asyncio
async def test_solver_solve_returns_agent_result():
    s = SolverAgent(llm=_OneShotLLM("结论：42"), registry=_make_registry(0))
    result = await s.solve(
        {"id": 1, "title": "T", "expected_output": "O", "suggested_tools": []}
    )
    assert hasattr(result, "answer") and hasattr(result, "steps")
    assert "42" in result.answer


@pytest.mark.asyncio
async def test_solver_arun_passes_history_through():
    s = SolverAgent(llm=_OneShotLLM("OK"), registry=_make_registry(0))
    history = [LLMMessage(role="system", content="ctx")]
    result = await s.arun(user_input="hello", history=history)
    assert result.answer == "OK"
