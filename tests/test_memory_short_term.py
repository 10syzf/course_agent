"""ShortTermMemory 单元测试."""

from __future__ import annotations

from typing import Any

import pytest

from course_agent.llm.base import BaseLLM, LLMMessage, LLMResponse
from course_agent.memory.short_term import ShortTermMemory


class _FakeLLM(BaseLLM):
    """记录所有 chat 调用，并返回固定摘要的伪 LLM."""

    def __init__(self) -> None:
        super().__init__(model="fake")
        self.calls: list[list[LLMMessage]] = []
        self.summary_text = "[summary] 用户和 Agent 聊了一些事情。"

    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self.calls.append(list(messages))
        return LLMResponse(content=self.summary_text)


@pytest.mark.asyncio
async def test_add_under_threshold_no_compress():
    llm = _FakeLLM()
    mem = ShortTermMemory(llm=llm, max_turns=10, compress_trigger=8)
    for i in range(4):
        await mem.add("user", f"q{i}")
        await mem.add("assistant", f"a{i}")
    assert len(llm.calls) == 0
    assert mem.summary is None
    assert mem.size == 8


@pytest.mark.asyncio
async def test_add_over_threshold_triggers_compress():
    llm = _FakeLLM()
    mem = ShortTermMemory(llm=llm, max_turns=10, compress_trigger=4)
    for i in range(5):
        await mem.add("user", f"q{i}")
    assert len(llm.calls) == 1, "超过 compress_trigger 后应触发一次摘要"
    assert mem.summary == llm.summary_text
    assert mem.size < 5, "压缩后应丢弃一半旧记录"


@pytest.mark.asyncio
async def test_compressed_history_includes_summary():
    llm = _FakeLLM()
    mem = ShortTermMemory(llm=llm, max_turns=4, compress_trigger=2)
    await mem.add("user", "u1")
    await mem.add("assistant", "a1")
    await mem.add("user", "u2")  # 触发压缩

    msgs = await mem.compressed_history()
    assert msgs[0].role == "system"
    assert "summary" in (msgs[0].content or "").lower() or "摘要" in (msgs[0].content or "")


@pytest.mark.asyncio
async def test_recall_returns_recent_in_reverse():
    mem = ShortTermMemory(llm=None)
    await mem.add("user", "first")
    await mem.add("assistant", "second")
    await mem.add("user", "third")
    res = await mem.recall("anything", k=2)
    assert [r.content for r in res] == ["third", "second"]


@pytest.mark.asyncio
async def test_clear_resets_everything():
    llm = _FakeLLM()
    mem = ShortTermMemory(llm=llm, compress_trigger=2)
    await mem.add("user", "u1")
    await mem.add("user", "u2")
    await mem.add("user", "u3")  # 触发压缩
    assert mem.summary is not None

    await mem.clear()
    assert mem.size == 0
    assert mem.summary is None


@pytest.mark.asyncio
async def test_no_llm_means_no_compression_just_storage():
    """LLM 为 None 时只做累加，不触发压缩."""
    mem = ShortTermMemory(llm=None, compress_trigger=2)
    for i in range(10):
        await mem.add("user", f"msg{i}")
    assert mem.summary is None
    assert mem.size == 10
