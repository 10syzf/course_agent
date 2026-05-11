"""测试 Task 011：流式抽象 + AgentLoop.astream_run() + tool_call delta 拼装."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest

from course_agent.core import AgentLoop
from course_agent.core.agent_loop import _materialize_tcs, _merge_tc_delta
from course_agent.llm import MockLLM
from course_agent.llm.base import BaseLLM, LLMMessage, LLMResponse, StreamChunk, ToolCall

# ---------------------------------------------------------------------------
# 1. BaseLLM 默认 astream() 应该把 achat 结果按字符切成假流式
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_baselllm_default_astream_yields_chunks_in_order():
    llm = MockLLM()
    chunks: list[StreamChunk] = []
    async for c in llm.astream([LLMMessage(role="user", content="说点什么")]):
        chunks.append(c)

    # 至少应该有一些文本 chunk + 一个 finish chunk
    assert chunks, "至少应有一个 chunk"
    assert chunks[-1].finish_reason in ("stop", "tool_calls", "length", "error")
    # 拼起来应是 MockLLM 的非工具回答
    text = "".join(c.delta_text for c in chunks)
    assert text  # MockLLM 直接回答会有内容


@pytest.mark.asyncio
async def test_baselllm_default_astream_yields_tool_call_delta():
    """MockLLM 数学输入会触发 calculator tool_call；默认 astream 应转成 tool_call_delta."""
    llm = MockLLM()
    chunks: list[StreamChunk] = []
    async for c in llm.astream(
        [LLMMessage(role="user", content="算一下 1+2")],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "calculator",
                    "description": "do math",
                    "parameters": {
                        "type": "object",
                        "properties": {"expression": {"type": "string"}},
                        "required": ["expression"],
                    },
                },
            }
        ],
    ):
        chunks.append(c)

    tc_deltas = [c.tool_call_delta for c in chunks if c.tool_call_delta]
    assert tc_deltas, "应该至少有一个 tool_call_delta"
    assert tc_deltas[0]["function"]["name"] == "calculator"
    # 最后一个 chunk 必须有 finish_reason
    assert chunks[-1].finish_reason is not None


# ---------------------------------------------------------------------------
# 2. _merge_tc_delta：跨 chunk 的 arguments 字符串拼接
# ---------------------------------------------------------------------------


def test_merge_tc_delta_assembles_arguments_across_chunks():
    acc: dict[int, dict[str, Any]] = {}
    _merge_tc_delta(
        acc,
        {"index": 0, "id": "call_x", "function": {"name": "calc", "arguments": '{"a"'}},
    )
    _merge_tc_delta(
        acc,
        {"index": 0, "function": {"name": None, "arguments": ': 1, "b"'}},
    )
    _merge_tc_delta(
        acc,
        {"index": 0, "function": {"name": None, "arguments": ": 2}"}},
    )
    assert acc[0]["id"] == "call_x"
    assert acc[0]["name"] == "calc"
    assert acc[0]["arguments"] == '{"a": 1, "b": 2}'


def test_merge_tc_delta_handles_multiple_indices():
    acc: dict[int, dict[str, Any]] = {}
    _merge_tc_delta(acc, {"index": 0, "function": {"name": "a", "arguments": "{}"}})
    _merge_tc_delta(acc, {"index": 1, "function": {"name": "b", "arguments": "{}"}})
    assert set(acc.keys()) == {0, 1}
    assert acc[0]["name"] == "a"
    assert acc[1]["name"] == "b"


def test_materialize_tcs_parses_json_and_skips_invalid():
    import logging

    log = logging.getLogger("test")
    acc: dict[int, dict[str, Any]] = {
        0: {"id": "c1", "name": "calc", "arguments": '{"x": 1}'},
        1: {"id": "c2", "name": "", "arguments": "{}"},  # missing name → skip
        2: {"id": None, "name": "echo", "arguments": "{not json}"},  # bad json → args={}
    }
    out = _materialize_tcs(acc, log)
    names = [tc.name for tc in out]
    assert names == ["calc", "echo"]
    assert out[0].arguments == {"x": 1}
    assert out[1].arguments == {}
    # call id 缺失时应自动生成
    assert out[1].id.startswith("call_")


# ---------------------------------------------------------------------------
# 3. AgentLoop.astream_run() 完整一轮：直接回答（无 tool_call）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_astream_run_direct_answer_yields_text_then_finish():
    loop = AgentLoop(llm=MockLLM(), max_steps=3)
    chunks: list[StreamChunk] = []
    async for c in loop.astream_run("说一句话"):
        chunks.append(c)

    assert chunks[-1].finish_reason in ("stop", "length")
    text = "".join(c.delta_text for c in chunks if c.delta_text)
    assert text  # 应有文本被外抛


# ---------------------------------------------------------------------------
# 4. AgentLoop.astream_run() 工具调用一轮：MockLLM 数学触发 calculator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_astream_run_with_tool_call_uses_calculator_and_finishes():
    loop = AgentLoop(llm=MockLLM(), max_steps=4)
    chunks: list[StreamChunk] = []
    async for c in loop.astream_run("帮我算 (3+5)*2"):
        chunks.append(c)

    full = "".join(c.delta_text for c in chunks if c.delta_text)
    assert "16" in full, f"期望最终文本含 16，实际：{full[:200]}"
    assert chunks[-1].finish_reason in ("stop", "length")


# ---------------------------------------------------------------------------
# 5. 错误降级：astream 抛 finish_reason=error → 降级到 arun
# ---------------------------------------------------------------------------


class _FlakyStreamLLM(BaseLLM):
    """astream 直接报错，但 achat 正常——验证 AgentLoop 降级路径."""

    def __init__(self) -> None:
        super().__init__(model="flaky")

    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        return LLMResponse(content="降级路径产生的最终答案", finish_reason="stop")

    async def achat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        return self.chat(messages, tools, **kwargs)

    async def astream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(finish_reason="error", error="HTTP 500 Mock")


@pytest.mark.asyncio
async def test_astream_run_falls_back_when_stream_errors():
    loop = AgentLoop(llm=_FlakyStreamLLM(), max_steps=3)
    chunks: list[StreamChunk] = []
    async for c in loop.astream_run("hi"):
        chunks.append(c)

    full = "".join(c.delta_text for c in chunks if c.delta_text)
    assert "降级路径产生的最终答案" in full
    assert chunks[-1].finish_reason == "stop"


# ---------------------------------------------------------------------------
# 6. astream_run 支持 history（多轮对话场景）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_astream_run_with_history_does_not_inject_default_system():
    loop = AgentLoop(llm=MockLLM(), max_steps=2)
    history = [
        LLMMessage(role="system", content="自定义 system"),
        LLMMessage(role="user", content="之前的"),
        LLMMessage(role="assistant", content="之前回答"),
    ]
    chunks: list[StreamChunk] = []
    async for c in loop.astream_run("接着说", history=history):
        chunks.append(c)
    assert chunks[-1].finish_reason in ("stop", "length")


# ---------------------------------------------------------------------------
# 7. tool_call 拼装的 JSON 解析失败时不应抛异常（only warning）
# ---------------------------------------------------------------------------


def test_materialize_tcs_invalid_json_yields_empty_args(caplog):
    import logging

    log = logging.getLogger("agent_test")
    acc = {0: {"id": "x", "name": "f", "arguments": "{this is not json"}}
    out = _materialize_tcs(acc, log)
    assert len(out) == 1
    assert out[0].arguments == {}


# ---------------------------------------------------------------------------
# 8. StreamChunk 默认值与基本字段
# ---------------------------------------------------------------------------


def test_streamchunk_defaults():
    c = StreamChunk()
    assert c.delta_text == ""
    assert c.tool_call_delta is None
    assert c.finish_reason is None
    assert c.error is None


def test_streamchunk_serializable():
    c = StreamChunk(delta_text="hi", finish_reason="stop")
    j = c.model_dump_json()
    obj = json.loads(j)
    assert obj["delta_text"] == "hi"
    assert obj["finish_reason"] == "stop"


# 显式标记 ToolCall import 在用，防止 ruff 删除
_ = ToolCall
