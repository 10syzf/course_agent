from __future__ import annotations

import pytest

from course_agent.core import AgentLoop
from course_agent.llm import MockLLM
from course_agent.memory.manager import MemoryManager
from course_agent.memory.short_term import ShortTermMemory
from course_agent.runtime.react_graph_runtime import ReactGraphRuntime
from course_agent.tools import get_registry


def test_agent_loop_saves_context_artifact(tmp_path):
    loop = AgentLoop(llm=MockLLM(), prompt_dir=str(tmp_path / 'prompts'), context_dir=str(tmp_path / 'contexts'))
    result = loop.run('你好')
    assert result.context_artifact_path
    assert loop.get_last_context() is not None


@pytest.mark.asyncio
async def test_agent_loop_with_memory_manager_collects_context_sections(tmp_path):
    mgr = MemoryManager(short=ShortTermMemory(llm=None), long=None)
    await mgr.add_user('之前的问题')
    loop = AgentLoop(
        llm=MockLLM(),
        memory_manager=mgr,
        prompt_dir=str(tmp_path / 'prompts'),
        context_dir=str(tmp_path / 'contexts'),
    )
    await loop.arun('继续')
    ctx = loop.get_last_context()
    assert ctx is not None
    assert any(s.source.startswith('short_memory') for s in ctx.sections)


def test_react_graph_runtime_saves_context_artifact(tmp_path):
    runtime = ReactGraphRuntime(
        llm=MockLLM(),
        registry=get_registry(),
        trace_dir=str(tmp_path / 'replays'),
        prompt_dir=str(tmp_path / 'prompts'),
        context_dir=str(tmp_path / 'contexts'),
    )
    result = runtime.run('你好')
    assert result.context_artifact_path
    assert runtime.get_last_context() is not None


@pytest.mark.asyncio
async def test_agent_loop_task_notes_enter_context(tmp_path):
    loop = AgentLoop(llm=MockLLM(), prompt_dir=str(tmp_path / 'prompts'), context_dir=str(tmp_path / 'contexts'))
    await loop.arun('做事', task_notes={'source': 'integration_test'})
    ctx = loop.get_last_context()
    assert ctx is not None
    assert any(s.name == 'task_notes' for s in ctx.sections)
