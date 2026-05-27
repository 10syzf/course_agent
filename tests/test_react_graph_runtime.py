"""Task 015：graph-native 单 Agent runtime 测试."""

from __future__ import annotations

import pytest

from course_agent.llm import MockLLM
from course_agent.llm.base import LLMMessage
from course_agent.runtime.react_graph_runtime import ReactGraphRuntime
from course_agent.tools import get_registry


def _runtime(tmp_path):
    return ReactGraphRuntime(
        llm=MockLLM(),
        registry=get_registry(),
        max_steps=4,
        trace_dir=str(tmp_path),
    )


def test_react_graph_runtime_run_direct_answer(tmp_path):
    runtime = _runtime(tmp_path)
    result = runtime.run("你好")
    assert result.answer
    assert result.runtime_kind == "react_graph"
    assert result.replay_path


def test_react_graph_runtime_run_tool_call_math(tmp_path):
    runtime = _runtime(tmp_path)
    result = runtime.run("帮我算一下 (3+5)*2")
    assert "16" in result.answer
    kinds = [item["kind"] for item in result.trace]
    assert "tool_call" in kinds


@pytest.mark.asyncio
async def test_react_graph_runtime_arun_with_history(tmp_path):
    runtime = _runtime(tmp_path)
    history = [
        LLMMessage(role="system", content="你是助手"),
        LLMMessage(role="user", content="之前问题"),
        LLMMessage(role="assistant", content="之前回答"),
    ]
    result = await runtime.arun("接着说", history=history)
    assert result.answer
    assert result.steps >= 1


@pytest.mark.asyncio
async def test_react_graph_runtime_astream_run_emits_stop(tmp_path):
    runtime = _runtime(tmp_path)
    chunks = []
    async for chunk in runtime.astream_run("你好"):
        chunks.append(chunk)
    assert chunks[-1].finish_reason == "stop"


def test_react_graph_runtime_get_graph_mermaid(tmp_path):
    runtime = _runtime(tmp_path)
    mermaid = runtime.get_graph_mermaid()
    assert "LLM" in mermaid or "llm" in mermaid


def test_react_graph_runtime_get_last_replay(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.run("你好")
    replay = runtime.get_last_replay()
    assert replay is not None
    assert replay["runtime_kind"] == "react_graph"


def test_react_graph_runtime_respects_max_steps(tmp_path):
    runtime = ReactGraphRuntime(
        llm=MockLLM(),
        registry=get_registry(),
        max_steps=1,
        trace_dir=str(tmp_path),
    )
    result = runtime.run("帮我算 1+2+3")
    assert result.steps <= 1


def test_react_graph_runtime_backend_is_langgraph(tmp_path):
    runtime = _runtime(tmp_path)
    assert runtime.backend == "langgraph"
