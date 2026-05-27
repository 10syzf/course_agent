from __future__ import annotations

import pytest

from course_agent.llm.base import LLMMessage
from course_agent.memory.embedders import HashEmbedder
from course_agent.memory.long_term import LongTermMemory
from course_agent.memory.manager import MemoryManager
from course_agent.memory.short_term import ShortTermMemory


@pytest.mark.asyncio
async def test_collect_context_sections_includes_short_memory_messages(tmp_path):
    mgr = MemoryManager(short=ShortTermMemory(llm=None), long=None)
    await mgr.add_user('u1')
    await mgr.add_assistant('a1')
    sections = await mgr.collect_context_sections('hello')
    assert any(s.source == 'short_memory_recent' for s in sections)


@pytest.mark.asyncio
async def test_collect_context_sections_includes_long_memory_hits(tmp_path):
    long_mem = LongTermMemory(embedder=HashEmbedder(), persist_dir=tmp_path / 'db', collection='ctx_policy')
    mgr = MemoryManager(short=ShortTermMemory(llm=None), long=long_mem, recall_min_score=0.0)
    await mgr.add_user('我喜欢 Python')
    sections = await mgr.collect_context_sections('Python')
    assert any(s.source == 'long_memory' for s in sections)


@pytest.mark.asyncio
async def test_enrich_context_still_keeps_system_message(tmp_path):
    mgr = MemoryManager(short=ShortTermMemory(llm=None), long=None)
    out = await mgr.enrich_context('hello', [LLMMessage(role='system', content='system prompt')])
    assert out[0].role == 'system'
    assert 'system prompt' in (out[0].content or '')


@pytest.mark.asyncio
async def test_remember_only_writes_long_memory(tmp_path):
    long_mem = LongTermMemory(embedder=HashEmbedder(), persist_dir=tmp_path / 'db2', collection='ctx_policy2')
    mgr = MemoryManager(short=ShortTermMemory(llm=None), long=long_mem)
    msg = await mgr.remember('用户偏好 Neovim', tag='preference')
    assert '已记住' in msg
    assert mgr.short.size == 0
