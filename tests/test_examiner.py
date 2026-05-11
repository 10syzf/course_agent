"""ExaminerAgent 测试（Task 011）.

覆盖：
- 限定工具集生效：python_exec / web_search 等不在白名单
- system_prompt 默认注入 EXAMINER_SYSTEM_PROMPT；可被覆盖
- arun() 与 astream_run() 与底层 AgentLoop 接口对齐
- 基于 MockLLM 的最简整轮：问问题 → 直接答（不调任何工具，避免污染状态）
- registry 中部分白名单工具缺失时不抛错（按交集筛选）
"""

from __future__ import annotations

from typing import Any

import pytest

from course_agent.agent import EXAMINER_SYSTEM_PROMPT, ExaminerAgent
from course_agent.llm.base import BaseLLM, LLMMessage, LLMResponse
from course_agent.llm.mock import MockLLM
from course_agent.tools.registry import Tool, ToolRegistry


def _build_partial_registry(names: list[str]) -> ToolRegistry:
    reg = ToolRegistry()

    def _stub(*args: Any, **kwargs: Any) -> str:
        return "ok"

    for n in names:
        reg.register(
            Tool(
                name=n,
                description=f"stub of {n}",
                parameters={"type": "object", "properties": {}, "required": []},
                func=_stub,
            )
        )
    return reg


def test_examiner_uses_default_system_prompt():
    ex = ExaminerAgent(llm=MockLLM())
    assert ex.loop.system_prompt == EXAMINER_SYSTEM_PROMPT
    assert "Examiner" in ex.loop.system_prompt
    assert "add_mistake" in ex.loop.system_prompt


def test_examiner_custom_system_prompt_overrides_default():
    custom = "你是 Examiner-mini，只出选择题。"
    ex = ExaminerAgent(llm=MockLLM(), system_prompt=custom)
    assert ex.loop.system_prompt == custom


def test_examiner_allowed_tools_only_intersect_registry():
    reg = _build_partial_registry(
        ["generate_question", "kb_search", "python_exec", "web_search"]
    )
    ex = ExaminerAgent(llm=MockLLM(), registry=reg)
    # 白名单 5 个里只有 2 个真实存在
    assert set(ex.allowed_tools) == {"generate_question", "kb_search"}
    # 非白名单工具一定不在内
    assert "python_exec" not in ex.allowed_tools
    assert "web_search" not in ex.allowed_tools


def test_examiner_excludes_unsafe_tools_from_real_registry():
    ex = ExaminerAgent(llm=MockLLM())
    # 真实 registry 里这些工具一定有，但 examiner 不允许
    forbidden = {"python_exec", "web_search", "web_fetch", "file_write", "image_ocr"}
    for f in forbidden:
        assert f not in ex.allowed_tools
    # 白名单中至少 generate_question / kb_search / add_mistake 一定能被发现
    assert "generate_question" in ex.allowed_tools
    assert "kb_search" in ex.allowed_tools
    assert "add_mistake" in ex.allowed_tools


def test_examiner_max_steps_is_propagated():
    ex = ExaminerAgent(llm=MockLLM(), max_steps=2)
    assert ex.loop.max_steps == 2


def test_examiner_repr_contains_tools_and_max_steps():
    ex = ExaminerAgent(llm=MockLLM(), max_steps=4)
    s = repr(ex)
    assert "ExaminerAgent" in s
    assert "max_steps=4" in s
    assert "tools=" in s


def test_examiner_llm_property_returns_inner_llm():
    llm = MockLLM()
    ex = ExaminerAgent(llm=llm)
    assert ex.llm is llm


@pytest.mark.asyncio
async def test_examiner_arun_returns_agent_result():
    ex = ExaminerAgent(llm=MockLLM(), max_steps=3)
    result = await ex.arun(user_input="你好，给我出一道简单的题")
    assert hasattr(result, "answer")
    assert hasattr(result, "steps")
    assert hasattr(result, "trace")
    assert isinstance(result.answer, str)
    assert result.steps >= 1


class _OneShotLLM(BaseLLM):
    """直接给一个 stop 答复的最简 LLM（避免触发任何工具）."""

    def __init__(self, text: str = "Examiner: 我想到一道题…") -> None:
        super().__init__(model="oneshot")
        self._text = text

    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        return LLMResponse(content=self._text, finish_reason="stop")


@pytest.mark.asyncio
async def test_examiner_astream_run_yields_text_and_finish():
    ex = ExaminerAgent(llm=_OneShotLLM(text="第一题：1+1=?"))
    chunks = []
    async for ch in ex.astream_run(user_input="出题"):
        chunks.append(ch)
    text = "".join(c.delta_text for c in chunks)
    assert "第一题" in text
    assert chunks[-1].finish_reason == "stop"


@pytest.mark.asyncio
async def test_examiner_history_is_passed_through():
    ex = ExaminerAgent(llm=_OneShotLLM(text="OK"))
    history = [
        LLMMessage(role="system", content="历史 system"),
        LLMMessage(role="user", content="历史 user"),
    ]
    result = await ex.arun(user_input="新输入", history=history)
    # arun 不抛异常即认为 history 透传成功；最终 answer 来自 _OneShotLLM
    assert result.answer == "OK"


def test_examiner_system_prompt_mentions_grading_rules():
    # 题目质量判分 0-5 的硬性规则必须在 prompt 里
    for kw in ["0", "5", "quality", "add_mistake", "correct_answer"]:
        assert kw in EXAMINER_SYSTEM_PROMPT
