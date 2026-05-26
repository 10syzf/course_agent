"""CriticAgent 单测（Task 012）.

覆盖：
- _parse_critic_json happy path
- score 越界裁剪到 [0, 5]
- pass 缺失时按 score>=3 推断
- 限定工具集仅保留 kb_search
- JSON 解析失败重试 1 次；仍失败 → 保守降级 pass=True
- happy path（LLM 返回合法 JSON）
- examiner.judge_answer 委托给 critic
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from course_agent.agent import CriticAgent, ExaminerAgent
from course_agent.agent.critic import (
    CRITIC_SYSTEM_PROMPT,
    _parse_critic_json,
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
    def __init__(self, replies: list[str]) -> None:
        super().__init__(model="fixed-critic")
        self._replies = list(replies)

    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        text = self._replies.pop(0) if self._replies else "{}"
        return LLMResponse(content=text, finish_reason="stop")


def test_parse_critic_json_happy_path():
    raw = json.dumps({"score": 4, "pass": True, "feedback": "不错"})
    out = _parse_critic_json(raw)
    assert out == {"score": 4, "pass": True, "feedback": "不错"}


def test_parse_critic_json_clips_out_of_range_score():
    assert _parse_critic_json(json.dumps({"score": 10, "pass": True}))["score"] == 5
    assert (
        _parse_critic_json(json.dumps({"score": -3, "pass": False}))["score"] == 0
    )


def test_parse_critic_json_infers_pass_from_score_when_missing():
    out = _parse_critic_json(json.dumps({"score": 4}))
    assert out is not None
    assert out["pass"] is True
    out2 = _parse_critic_json(json.dumps({"score": 1}))
    assert out2 is not None
    assert out2["pass"] is False


def test_parse_critic_json_invalid_inputs_return_none():
    assert _parse_critic_json("") is None
    assert _parse_critic_json("not json") is None
    # 缺 score 字段
    assert _parse_critic_json(json.dumps({"pass": True})) is None
    # score 非数字
    assert _parse_critic_json(json.dumps({"score": "abc"})) is None


def test_parse_critic_json_handles_markdown_fence():
    raw = (
        "评分如下：\n```json\n"
        + json.dumps({"score": 3, "pass": True, "feedback": "ok"})
        + "\n```"
    )
    out = _parse_critic_json(raw)
    assert out and out["score"] == 3


def test_critic_allowed_tools_only_kb_search_subset():
    reg = _registry_with(["kb_search", "python_exec", "web_search"])
    c = CriticAgent(llm=MockLLM(), registry=reg)
    assert c.allowed_tools == ["kb_search"]


def test_critic_system_prompt_mentions_score_and_pass():
    assert "score" in CRITIC_SYSTEM_PROMPT
    assert "pass" in CRITIC_SYSTEM_PROMPT
    assert "feedback" in CRITIC_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_critic_happy_path_returns_parsed_dict():
    raw = json.dumps({"score": 5, "pass": True, "feedback": "完美"})
    c = CriticAgent(llm=_FixedLLM([raw]), registry=_registry_with([]))
    result = await c.critique(
        {"id": 1, "title": "T", "expected_output": "O"}, "学生的答案"
    )
    assert result["score"] == 5
    assert result["pass"] is True


@pytest.mark.asyncio
async def test_critic_retries_once_then_succeeds():
    bad = "我认为评分是 3"
    good = json.dumps({"score": 3, "pass": True, "feedback": "可以"})
    c = CriticAgent(llm=_FixedLLM([bad, good]), registry=_registry_with([]))
    result = await c.critique({"id": 1, "title": "T", "expected_output": "O"}, "X")
    assert result["score"] == 3


@pytest.mark.asyncio
async def test_critic_conservative_fallback_when_both_attempts_fail():
    c = CriticAgent(
        llm=_FixedLLM(["乱码", "继续乱码"]),
        registry=_registry_with([]),
    )
    result = await c.critique(
        {"id": 1, "title": "T", "expected_output": "O"}, "X"
    )
    assert result["pass"] is True
    assert result["score"] == 3
    assert "解析失败" in result["feedback"] or "默认通过" in result["feedback"]


@pytest.mark.asyncio
async def test_examiner_judge_answer_delegates_to_critic():
    raw = json.dumps({"score": 4, "pass": True, "feedback": "很好"})
    critic = CriticAgent(llm=_FixedLLM([raw]), registry=_registry_with([]))
    ex = ExaminerAgent(llm=MockLLM(), critic=critic)
    out = await ex.judge_answer(
        question="1+1=?", correct_answer="2", student_answer="2"
    )
    assert out["score"] == 4
    assert out["pass"] is True
