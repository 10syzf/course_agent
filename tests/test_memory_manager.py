"""MemoryManager 单元测试."""

from __future__ import annotations

import pytest

from course_agent.llm.base import LLMMessage
from course_agent.memory.embedders import HashEmbedder
from course_agent.memory.long_term import LongTermMemory
from course_agent.memory.manager import MemoryManager
from course_agent.memory.short_term import ShortTermMemory


def _build_manager(tmp_path, *, with_long: bool = True) -> MemoryManager:
    short = ShortTermMemory(llm=None, max_turns=10, compress_trigger=8)
    long_mem = (
        LongTermMemory(
            embedder=HashEmbedder(),
            persist_dir=tmp_path / "chroma",
            collection="mgr_test",
        )
        if with_long
        else None
    )
    return MemoryManager(
        short=short,
        long=long_mem,
        recall_k=3,
        recall_min_score=0.0,
    )


@pytest.mark.asyncio
async def test_enrich_context_keeps_system_prompt(tmp_path):
    mgr = _build_manager(tmp_path, with_long=False)
    base = [
        LLMMessage(role="system", content="你是 Course Agent"),
    ]
    out = await mgr.enrich_context("hello", base)
    assert out[0].role == "system"
    assert "Course Agent" in (out[0].content or "")


@pytest.mark.asyncio
async def test_enrich_context_injects_relevant_memories(tmp_path):
    mgr = _build_manager(tmp_path, with_long=True)
    await mgr.add_user("我最喜欢的语言是 Python")
    await mgr.add_assistant("好的，记住了你喜欢 Python")

    base = [LLMMessage(role="system", content="system")]
    out = await mgr.enrich_context("我应该用什么语言写算法题 Python", base)

    relevant_msgs = [m for m in out if "RELEVANT MEMORIES" in (m.content or "")]
    assert len(relevant_msgs) >= 1
    assert "Python" in (relevant_msgs[0].content or "")


@pytest.mark.asyncio
async def test_add_user_writes_both_short_and_long(tmp_path):
    mgr = _build_manager(tmp_path, with_long=True)
    await mgr.add_user("important fact")
    assert mgr.short.size == 1
    assert mgr.long is not None and mgr.long.count() == 1


@pytest.mark.asyncio
async def test_remember_only_writes_long(tmp_path):
    mgr = _build_manager(tmp_path, with_long=True)
    msg = await mgr.remember("用户偏好 vim", tag="preference")
    assert "已记住" in msg
    assert mgr.short.size == 0
    assert mgr.long is not None and mgr.long.count() == 1


@pytest.mark.asyncio
async def test_remember_without_long_returns_warning(tmp_path):
    mgr = _build_manager(tmp_path, with_long=False)
    msg = await mgr.remember("anything")
    assert "未启用" in msg


@pytest.mark.asyncio
async def test_recall_returns_records(tmp_path):
    mgr = _build_manager(tmp_path, with_long=True)
    await mgr.add_user("alpha beta gamma delta")
    res = await mgr.recall("alpha beta", k=2)
    assert len(res) >= 1
    assert "alpha" in res[0].content


@pytest.mark.asyncio
async def test_clear_short_and_long(tmp_path):
    mgr = _build_manager(tmp_path, with_long=True)
    await mgr.add_user("x")
    await mgr.add_assistant("y")
    assert mgr.short.size == 2
    assert mgr.long is not None and mgr.long.count() == 2

    await mgr.clear_short()
    assert mgr.short.size == 0
    assert mgr.long.count() == 2  # 长期保留

    await mgr.clear_long()
    assert mgr.long.count() == 0
