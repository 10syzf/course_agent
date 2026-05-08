"""测试 Agent Loop 端到端流程（使用 MockLLM）."""

from __future__ import annotations

from course_agent.core import AgentLoop
from course_agent.llm import MockLLM


def test_agent_loop_math():
    loop = AgentLoop(llm=MockLLM(), max_steps=5)
    result = loop.run("帮我算一下 (3+5)*2 等于多少")
    assert result.steps >= 1
    assert "16" in result.answer


def test_agent_loop_direct_answer():
    loop = AgentLoop(llm=MockLLM(), max_steps=3)
    result = loop.run("你好，请做个自我介绍")
    assert result.steps >= 1
    assert result.answer


def test_agent_loop_web_search():
    loop = AgentLoop(llm=MockLLM(), max_steps=5)
    result = loop.run("帮我搜索一下 Transformer 架构")
    trace_kinds = [t["kind"] for t in result.trace]
    assert "tool_call" in trace_kinds
    assert "tool_result" in trace_kinds


def test_agent_loop_respects_max_steps():
    loop = AgentLoop(llm=MockLLM(), max_steps=1)
    result = loop.run("帮我算 1+2+3")
    assert result.steps <= 1
