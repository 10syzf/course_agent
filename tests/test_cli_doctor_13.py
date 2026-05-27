"""Task 014：doctor 第 13 项测试."""

from __future__ import annotations

from typer.testing import CliRunner

from course_agent import config as cfgmod
from course_agent.cli import _check_langgraph_runtime, app
from course_agent.config import AgentConfig, AppConfig, LLMConfig, LoggingConfig, RuntimeConfig
from course_agent.mcp.config import MCPConfig

runner = CliRunner()


def _cfg(provider: str = "mock") -> AppConfig:
    return AppConfig(
        llm=LLMConfig(provider=provider, model="mock-llm"),
        agent=AgentConfig(max_steps=6),
        runtime=RuntimeConfig(backend="langgraph", checkpoint="memory", draw_graph=True),
        mcp=MCPConfig(),
        logging=LoggingConfig(),
    )


def test_check_13_langgraph_runtime_with_mock():
    status, detail, hint = _check_langgraph_runtime(_cfg("mock"))
    assert status == "⚠️"
    assert "graph OK" in detail
    assert "Mermaid" in hint


def test_check_13_langgraph_runtime_with_no_key_still_roundtrips():
    cfg = _cfg("openai")
    cfg.llm.api_key = None
    status, detail, hint = _check_langgraph_runtime(cfg)
    assert status == "⚠️"
    assert "graph OK" in detail


def test_doctor_command_includes_langgraph_check():
    cfgmod._config = None
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code in (0, 1)
    assert "LangGraph Runtime" in result.stdout
    assert "13/" in result.stdout or " 13 " in result.stdout


def test_doctor_command_with_langgraph_backend_env_not_crash(monkeypatch):
    cfgmod._config = None
    monkeypatch.setenv("RUNTIME_BACKEND", "langgraph")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code in (0, 1)
