"""generate_question 工具测试（Task 011）.

覆盖：
- 工具已注册且 schema 合法
- 输入校验：非法 question_type / difficulty / n_refs 兜底
- LLM 返回合法 JSON → markdown 输出含 question + correct 块 + 出处
- LLM 第一次返回非 JSON → 第二次成功（重试 1 次路径）
- LLM 两次都失败 → 友好降级提示（不抛异常）
- kb_search 抛异常时友好降级（refs 为空也能出题）
- based_on_mistakes 字段会出现在 markdown 中
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from course_agent.llm.base import BaseLLM, LLMMessage, LLMResponse
from course_agent.tools import get_registry
from course_agent.tools.generator import (
    _build_user_prompt,
    _format_markdown,
    _parse_json_safe,
    generate_question,
)


class _FakeLLM(BaseLLM):
    """依次返回预设 content 的假 LLM."""

    def __init__(self, replies: list[str]) -> None:
        super().__init__(model="fake")
        self._replies = list(replies)
        self.calls: list[list[LLMMessage]] = []

    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self.calls.append(list(messages))
        if not self._replies:
            return LLMResponse(content="", finish_reason="stop")
        return LLMResponse(content=self._replies.pop(0), finish_reason="stop")


_GOOD_JSON = json.dumps(
    {
        "question": "求矩阵 A=[[2,1],[1,2]] 的特征值。",
        "correct_answer": "λ1=3, λ2=1",
        "explanation": "解 det(A-λI)=0 即可。",
        "source": "线代教材 P.83",
        "based_on_mistakes": [1, 2],
        "type": "解答题",
        "difficulty": "中",
    },
    ensure_ascii=False,
)


def test_generate_question_registered_in_registry():
    reg = get_registry()
    assert "generate_question" in reg.list_names()
    schema = reg.get("generate_question").to_openai_schema()
    fn = schema["function"]
    assert fn["name"] == "generate_question"
    assert "tag" in fn["parameters"]["properties"]
    assert "question_type" in fn["parameters"]["properties"]
    assert "difficulty" in fn["parameters"]["properties"]


def test_parse_json_safe_handles_pure_json_and_partial_fence():
    # 1) 纯 JSON 直接解析
    obj = _parse_json_safe(_GOOD_JSON)
    assert obj is not None
    assert obj["question"].startswith("求矩阵")
    # 2) 文本前后带噪声但内含完整 {…} → 通过 find/rfind 兜底
    raw = "好的，下面是题目：\n" + _GOOD_JSON + "\n请查收"
    obj2 = _parse_json_safe(raw)
    assert obj2 is not None
    assert obj2["question"].startswith("求矩阵")


def test_parse_json_safe_returns_none_on_garbage():
    assert _parse_json_safe("这不是 JSON") is None
    assert _parse_json_safe("") is None
    assert _parse_json_safe("{ not valid }") is None


def test_format_markdown_contains_correct_block_and_source():
    obj = json.loads(_GOOD_JSON)
    md = _format_markdown(obj)
    assert "新题" in md
    assert "求矩阵" in md
    assert "线代教材 P.83" in md
    assert "```correct" in md
    assert "λ1=3" in md
    assert "#1" in md and "#2" in md


def test_build_user_prompt_includes_avoid_repeat_section():
    past = [{"id": 9, "question": "旧题：求 A 的迹"}]
    text = _build_user_prompt("线代", "解答题", "中", "教材片段X", past)
    assert "线代" in text
    assert "教材片段X" in text
    assert "#9" in text and "旧题" in text


def test_build_user_prompt_handles_empty_past_mistakes():
    text = _build_user_prompt("微积分", "选择题", "简单", "", [])
    assert "暂无过往错题" in text
    assert "暂无可用教材片段" in text


def test_generate_question_happy_path():
    fake = _FakeLLM([_GOOD_JSON])
    with (
        patch("course_agent.tools.generator.get_default_llm", return_value=fake),
        patch("course_agent.tools.generator.kb_search", return_value="📚 参考片段"),
        patch(
            "course_agent.tools.generator._query_past_mistakes", return_value=[]
        ),
    ):
        out = generate_question(tag="线代,特征值", question_type="解答题", difficulty="中", n_refs=2)
    assert "新题" in out
    assert "求矩阵" in out
    assert "```correct" in out
    assert len(fake.calls) == 1


def test_generate_question_retries_on_invalid_json_first_time():
    fake = _FakeLLM(["这不是 JSON 是垃圾", _GOOD_JSON])
    with (
        patch("course_agent.tools.generator.get_default_llm", return_value=fake),
        patch("course_agent.tools.generator.kb_search", return_value=""),
        patch(
            "course_agent.tools.generator._query_past_mistakes", return_value=[]
        ),
    ):
        out = generate_question(tag="线代")
    assert "求矩阵" in out
    assert len(fake.calls) == 2
    # 重试时应包含再次提示
    last_user = fake.calls[1][-1].content
    assert "无法解析为 JSON" in last_user


def test_generate_question_friendly_fallback_when_both_fail():
    fake = _FakeLLM(["垃圾1", "垃圾2"])
    with (
        patch("course_agent.tools.generator.get_default_llm", return_value=fake),
        patch("course_agent.tools.generator.kb_search", return_value=""),
        patch(
            "course_agent.tools.generator._query_past_mistakes", return_value=[]
        ),
    ):
        out = generate_question(tag="线代")
    assert "题目生成失败" in out or "⚠️" in out
    assert "垃圾" in out  # 截断后仍可见原始响应片段


def test_generate_question_handles_kb_search_exception():
    fake = _FakeLLM([_GOOD_JSON])
    with (
        patch("course_agent.tools.generator.get_default_llm", return_value=fake),
        patch(
            "course_agent.tools.generator.kb_search",
            side_effect=RuntimeError("kb 挂了"),
        ),
        patch(
            "course_agent.tools.generator._query_past_mistakes", return_value=[]
        ),
    ):
        out = generate_question(tag="线代")
    # 不抛异常，且仍能给出题目
    assert "求矩阵" in out


def test_generate_question_invalid_inputs_fall_back_to_defaults():
    fake = _FakeLLM([_GOOD_JSON])
    with (
        patch("course_agent.tools.generator.get_default_llm", return_value=fake),
        patch("course_agent.tools.generator.kb_search", return_value=""),
        patch(
            "course_agent.tools.generator._query_past_mistakes", return_value=[]
        ),
    ):
        out = generate_question(
            tag="X",
            question_type="奇怪的题型",
            difficulty="超难",
            n_refs="abc",  # type: ignore[arg-type]
        )
    # 仍返回题目 markdown（不抛 ValueError）
    assert "新题" in out


@pytest.mark.parametrize("n_refs,expected_arg", [(0, 1), (3, 3), (99, 6), (-5, 1)])
def test_generate_question_clamps_n_refs(n_refs, expected_arg):
    fake = _FakeLLM([_GOOD_JSON])
    captured = {}

    def fake_kb(query: str, top_k: int = 3) -> str:
        captured["top_k"] = top_k
        return ""

    with (
        patch("course_agent.tools.generator.get_default_llm", return_value=fake),
        patch("course_agent.tools.generator.kb_search", side_effect=fake_kb),
        patch(
            "course_agent.tools.generator._query_past_mistakes", return_value=[]
        ),
    ):
        generate_question(tag="X", n_refs=n_refs)
    assert captured.get("top_k") == expected_arg


def test_generate_question_includes_past_mistake_ids_in_prompt():
    fake = _FakeLLM([_GOOD_JSON])
    past = [{"id": 7, "question": "求 det(A)"}]
    with (
        patch("course_agent.tools.generator.get_default_llm", return_value=fake),
        patch("course_agent.tools.generator.kb_search", return_value=""),
        patch(
            "course_agent.tools.generator._query_past_mistakes", return_value=past
        ),
    ):
        generate_question(tag="线代")
    user_msg = fake.calls[0][-1].content
    assert "#7" in user_msg
    assert "求 det(A)" in user_msg
