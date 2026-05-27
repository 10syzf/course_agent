"""Task 015：react graph 节点测试."""

from __future__ import annotations

import pytest

from course_agent.graph.react_nodes import (
    finalize_node,
    llm_node,
    prepare_context_node,
    tool_node,
)
from course_agent.llm import MockLLM
from course_agent.llm.base import LLMMessage
from course_agent.tools import get_registry


@pytest.mark.asyncio
async def test_prepare_context_node_adds_trace():
    out = await prepare_context_node({"messages": [], "trace": []})
    assert out["trace"][0]["node"] == "prepare_context"


@pytest.mark.asyncio
async def test_llm_node_returns_final_when_no_tool_calls():
    out = await llm_node(
        {"messages": [LLMMessage(role="user", content="你好").model_dump()], "steps": 0, "trace": []},
        llm=MockLLM(),
        tool_schemas=[],
    )
    assert out["done"] is True
    assert out["final_answer"]


@pytest.mark.asyncio
async def test_llm_node_returns_pending_tool_calls_for_math():
    reg = get_registry()
    out = await llm_node(
        {"messages": [LLMMessage(role="user", content="帮我算一下 (3+5)*2").model_dump()], "steps": 0, "trace": []},
        llm=MockLLM(),
        tool_schemas=reg.to_openai_schemas(["calculator"]),
    )
    assert out["done"] is False
    assert out["pending_tool_calls"][0]["name"] == "calculator"


@pytest.mark.asyncio
async def test_tool_node_executes_pending_tools():
    out = await tool_node(
        {
            "messages": [],
            "pending_tool_calls": [{"id": "1", "name": "calculator", "arguments": {"expression": "(3+5)*2"}}],
            "tool_results": [],
            "trace": [],
            "steps": 1,
        },
        registry=get_registry(),
    )
    assert "16" in out["tool_results"][0]["result"]
    assert out["messages"][0]["role"] == "tool"


@pytest.mark.asyncio
async def test_finalize_node_uses_existing_final_answer():
    out = await finalize_node({"final_answer": "ok", "trace": [], "max_steps": 4})
    assert out["final_answer"] == "ok"


@pytest.mark.asyncio
async def test_finalize_node_generates_timeout_message_when_missing():
    out = await finalize_node({"messages": [], "trace": [], "max_steps": 4})
    assert "最大步数" in out["final_answer"]
