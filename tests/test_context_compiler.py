from __future__ import annotations

import pytest

from course_agent.context import ContextBudget, compile_context, render_context_messages
from course_agent.llm.base import LLMMessage
from course_agent.memory.manager import MemoryManager
from course_agent.memory.short_term import ShortTermMemory


@pytest.mark.asyncio
async def test_compile_context_keeps_history_sections():
    prompt, ctx = await compile_context(
        role='react',
        role_prompt='你是助手',
        user_input='你好',
        history=[LLMMessage(role='user', content='old q'), LLMMessage(role='assistant', content='old a')],
    )
    assert prompt.role == 'react'
    assert any(s.source == 'history' for s in ctx.sections)


@pytest.mark.asyncio
async def test_compile_context_adds_task_and_session_notes():
    _, ctx = await compile_context(
        role='solver',
        role_prompt='你是 solver',
        user_input='执行任务',
        session_notes={'session_id': 's1'},
        task_notes={'source': 'unit_test'},
    )
    names = [s.name for s in ctx.sections]
    assert 'session_notes' in names
    assert 'task_notes' in names


@pytest.mark.asyncio
async def test_compile_context_uses_memory_manager_sections():
    short = ShortTermMemory(llm=None)
    mgr = MemoryManager(short=short, long=None)
    await mgr.add_user('用户喜欢 Python')
    _, ctx = await compile_context(
        role='react',
        role_prompt='你是助手',
        user_input='我喜欢什么语言',
        memory_manager=mgr,
    )
    assert any(s.source.startswith('short_memory') for s in ctx.sections)


@pytest.mark.asyncio
async def test_compile_context_respects_budget_and_drops_some_sections():
    history = [LLMMessage(role='user', content='x' * 120), LLMMessage(role='assistant', content='y' * 120)]
    _, ctx = await compile_context(
        role='react',
        role_prompt='你是助手',
        user_input='测试',
        history=history,
        budget=ContextBudget(max_chars=80, reserve_chars=0),
    )
    assert ctx.selected_chars <= 80
    assert ctx.dropped_sections or ctx.compression_trace


@pytest.mark.asyncio
async def test_render_context_messages_preserves_roles():
    _, ctx = await compile_context(
        role='react',
        role_prompt='你是助手',
        user_input='测试',
        history=[LLMMessage(role='assistant', content='old a')],
    )
    msgs = render_context_messages(ctx)
    assert any(m.role == 'assistant' for m in msgs)
