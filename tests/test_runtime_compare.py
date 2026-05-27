"""Task 015：legacy vs langgraph chat runtime 对比测试."""

from __future__ import annotations

from course_agent.config import (
    AgentConfig,
    AppConfig,
    LLMConfig,
    LoggingConfig,
    RuntimeConfig,
)
from course_agent.llm import MockLLM
from course_agent.mcp.config import MCPConfig
from course_agent.runtime import create_chat_runtime
from course_agent.tools import get_registry


def _cfg(agent_loop_backend: str = "legacy") -> AppConfig:
    return AppConfig(
        llm=LLMConfig(provider="mock", model="mock-llm"),
        agent=AgentConfig(max_steps=4),
        runtime=RuntimeConfig(
            backend="langgraph",
            agent_loop_backend=agent_loop_backend,
            checkpoint="memory",
            draw_graph=True,
            trace_dir="data/replays",
        ),
        mcp=MCPConfig(),
        logging=LoggingConfig(),
    )


def test_create_chat_runtime_legacy():
    runtime = create_chat_runtime(_cfg("legacy"), llm=MockLLM(), registry=get_registry())
    assert runtime.__class__.__name__ == "AgentLoop"


def test_create_chat_runtime_langgraph():
    runtime = create_chat_runtime(_cfg("langgraph"), llm=MockLLM(), registry=get_registry())
    assert runtime.__class__.__name__ == "ReactGraphRuntime"


def test_legacy_and_langgraph_answer_same_math_shape(tmp_path):
    cfg = _cfg("legacy")
    legacy = create_chat_runtime(cfg, llm=MockLLM(), registry=get_registry())
    graph = create_chat_runtime(
        _cfg("langgraph"),
        llm=MockLLM(),
        registry=get_registry(),
        trace_dir=str(tmp_path),
    )
    a1 = legacy.run("帮我算一下 (3+5)*2").answer
    a2 = graph.run("帮我算一下 (3+5)*2").answer
    assert "16" in a1
    assert "16" in a2


def test_legacy_and_langgraph_direct_answer_both_non_empty(tmp_path):
    legacy = create_chat_runtime(_cfg("legacy"), llm=MockLLM(), registry=get_registry())
    graph = create_chat_runtime(
        _cfg("langgraph"),
        llm=MockLLM(),
        registry=get_registry(),
        trace_dir=str(tmp_path),
    )
    assert legacy.run("你好").answer
    assert graph.run("你好").answer
