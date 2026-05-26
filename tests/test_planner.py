"""PlannerAgent 单测（Task 012）.

覆盖：
- _parse_plan_json 各类输入（裸 JSON / ``` ``` 包裹 / 解释前缀 / 空 / 非法）
- 限定工具集只保留白名单交集
- 解析失败 → 单 sub_task 降级
- sub_tasks 数 > max_sub_tasks 时截断
- happy path：JSON 输出 → 多 sub_task
- system_prompt 含约束关键词
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from course_agent.agent import PlannerAgent
from course_agent.agent.planner import (
    PLANNER_SYSTEM_PROMPT,
    _parse_plan_json,
)
from course_agent.llm.base import BaseLLM, LLMMessage, LLMResponse
from course_agent.llm.mock import MockLLM
from course_agent.tools.registry import Tool, ToolRegistry


def _registry_with(names: list[str]) -> ToolRegistry:
    reg = ToolRegistry()
    for n in names:
        reg.register(
            Tool(
                name=n,
                description=f"stub {n}",
                parameters={"type": "object", "properties": {}, "required": []},
                func=lambda **_: "ok",
            )
        )
    return reg


class _FixedLLM(BaseLLM):
    """按调用顺序返回预设答复."""

    def __init__(self, replies: list[str]) -> None:
        super().__init__(model="fixed-planner")
        self._replies = list(replies)

    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        text = self._replies.pop(0) if self._replies else "{}"
        return LLMResponse(content=text, finish_reason="stop")


def test_parse_plan_json_naked_json_ok():
    raw = json.dumps(
        {
            "plan_summary": "x",
            "sub_tasks": [
                {"id": 1, "title": "a", "expected_output": "out"},
                {"id": 2, "title": "b", "expected_output": "out2"},
            ],
        }
    )
    out = _parse_plan_json(raw)
    assert out and len(out) == 2
    assert out[0]["title"] == "a"
    assert out[1]["expected_output"] == "out2"


def test_parse_plan_json_handles_markdown_fence():
    raw = (
        "好的：\n```json\n"
        + json.dumps({"sub_tasks": [{"id": 1, "title": "X"}]})
        + "\n```"
    )
    out = _parse_plan_json(raw)
    assert out and out[0]["title"] == "X"
    # expected_output 应自动填默认值
    assert out[0]["expected_output"]


def test_parse_plan_json_invalid_returns_none():
    assert _parse_plan_json("") is None
    assert _parse_plan_json("not json at all") is None
    assert _parse_plan_json("{}") is None
    assert _parse_plan_json('{"sub_tasks": []}') is None
    assert _parse_plan_json('{"sub_tasks": "not a list"}') is None


def test_planner_allowed_tools_intersect_only():
    reg = _registry_with(["kb_search", "python_exec", "web_search"])
    p = PlannerAgent(llm=MockLLM(), registry=reg)
    assert "kb_search" in p.allowed_tools
    assert "python_exec" not in p.allowed_tools
    assert "web_search" not in p.allowed_tools
    # list_mistakes 在 registry 里没有，也不该出现
    assert "list_mistakes" not in p.allowed_tools


def test_planner_system_prompt_mentions_constraints():
    assert "JSON" in PLANNER_SYSTEM_PROMPT
    assert "sub_task" in PLANNER_SYSTEM_PROMPT
    assert "5" in PLANNER_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_planner_happy_path_returns_sub_tasks():
    raw = json.dumps(
        {
            "plan_summary": "summary",
            "sub_tasks": [
                {"id": 1, "title": "step1", "expected_output": "结论1"},
                {"id": 2, "title": "step2", "expected_output": "结论2"},
            ],
        }
    )
    p = PlannerAgent(llm=_FixedLLM([raw]), registry=_registry_with([]))
    sub_tasks = await p.plan("帮我做实验报告")
    assert len(sub_tasks) == 2
    assert sub_tasks[0]["title"] == "step1"
    assert sub_tasks[1]["id"] == 2


@pytest.mark.asyncio
async def test_planner_retries_once_on_bad_json_then_succeeds():
    bad = "我先解释一下。"
    good = json.dumps({"sub_tasks": [{"id": 1, "title": "T", "expected_output": "O"}]})
    p = PlannerAgent(llm=_FixedLLM([bad, good]), registry=_registry_with([]))
    sub_tasks = await p.plan("X")
    assert len(sub_tasks) == 1
    assert sub_tasks[0]["title"] == "T"


@pytest.mark.asyncio
async def test_planner_falls_back_to_single_subtask_when_both_attempts_fail():
    p = PlannerAgent(
        llm=_FixedLLM(["乱七八糟", "还是乱七八糟"]),
        registry=_registry_with([]),
    )
    sub_tasks = await p.plan("做个简单计算")
    assert len(sub_tasks) == 1
    assert "做个简单计算" in sub_tasks[0]["title"]


@pytest.mark.asyncio
async def test_planner_truncates_when_exceeds_max():
    big = json.dumps(
        {
            "sub_tasks": [
                {"id": i, "title": f"t{i}", "expected_output": "x"}
                for i in range(1, 9)
            ]
        }
    )
    p = PlannerAgent(
        llm=_FixedLLM([big]),
        registry=_registry_with([]),
        max_sub_tasks=3,
    )
    sub_tasks = await p.plan("X")
    assert len(sub_tasks) == 3
