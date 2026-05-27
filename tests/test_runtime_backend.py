"""Task 014：双运行时入口测试."""

from __future__ import annotations

from course_agent.config import AgentConfig, AppConfig, LLMConfig, LoggingConfig, RuntimeConfig
from course_agent.llm import MockLLM
from course_agent.mcp.config import MCPConfig
from course_agent.runtime import create_runtime
from course_agent.runtime.backend import RuntimeBackend
from course_agent.runtime.langgraph_runtime import LangGraphRuntime
from course_agent.runtime.legacy_runtime import LegacyRuntime
from course_agent.tools.registry import ToolRegistry


def _cfg(backend: str = "legacy") -> AppConfig:
    return AppConfig(
        llm=LLMConfig(provider="mock", model="mock-llm"),
        agent=AgentConfig(max_steps=6),
        runtime=RuntimeConfig(backend=backend, checkpoint="memory", draw_graph=True),
        mcp=MCPConfig(),
        logging=LoggingConfig(),
    )


def test_runtime_backend_enum_values():
    assert RuntimeBackend.LEGACY.value == "legacy"
    assert RuntimeBackend.LANGGRAPH.value == "langgraph"


def test_create_runtime_defaults_to_legacy_when_runtime_missing():
    class _Cfg:
        llm = LLMConfig(provider="mock", model="mock-llm")
        agent = AgentConfig(max_steps=5)

    runtime = create_runtime(_Cfg(), llm=MockLLM(), registry=ToolRegistry())
    assert isinstance(runtime, LegacyRuntime)


def test_create_runtime_from_cfg_legacy():
    runtime = create_runtime(_cfg("legacy"), llm=MockLLM(), registry=ToolRegistry())
    assert isinstance(runtime, LegacyRuntime)
    assert runtime.backend == "legacy"


def test_create_runtime_from_cfg_langgraph():
    runtime = create_runtime(_cfg("langgraph"), llm=MockLLM(), registry=ToolRegistry())
    assert isinstance(runtime, LangGraphRuntime)
    assert runtime.backend == "langgraph"


def test_create_runtime_backend_argument_overrides_cfg():
    runtime = create_runtime(
        _cfg("legacy"),
        llm=MockLLM(),
        registry=ToolRegistry(),
        backend="langgraph",
    )
    assert isinstance(runtime, LangGraphRuntime)


def test_create_runtime_passes_draw_graph_and_checkpoint():
    runtime = create_runtime(_cfg("langgraph"), llm=MockLLM(), registry=ToolRegistry())
    assert runtime.checkpoint == "memory"
    assert runtime.draw_graph is True


def test_create_runtime_uses_agent_max_steps_for_solver_default():
    runtime = create_runtime(_cfg("langgraph"), llm=MockLLM(), registry=ToolRegistry())
    assert runtime.orchestrator.solver.loop.max_steps == 6
