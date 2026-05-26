"""CLI capabilities / skills / mcp 单测（Task 013）."""

from __future__ import annotations

from typer.testing import CliRunner

from course_agent import config as cfgmod
from course_agent.cli import app

runner = CliRunner()


def test_capabilities_command_lists_skill_and_tools(monkeypatch):
    cfgmod._config = None
    monkeypatch.setenv("MCP_ENABLED", "false")
    result = runner.invoke(app, ["capabilities"])
    assert result.exit_code == 0
    assert "统一 Capability 列表" in result.stdout
    assert "skills" in result.stdout
    assert "internal_tool" in result.stdout


def test_skills_list_command_lists_builtins():
    result = runner.invoke(app, ["skills", "list"])
    assert result.exit_code == 0
    assert "study_plan_skill" in result.stdout
    assert "quiz_from_notes_skill" in result.stdout


def test_mcp_list_disabled_shows_friendly_message(monkeypatch):
    cfgmod._config = None
    monkeypatch.setenv("MCP_ENABLED", "false")
    result = runner.invoke(app, ["mcp", "list"])
    assert result.exit_code == 0
    assert "未启用" in result.stdout or "MCP" in result.stdout


def test_mcp_list_enabled_lists_mock_tools(monkeypatch):
    cfgmod._config = None
    monkeypatch.setenv("MCP_ENABLED", "true")
    result = runner.invoke(app, ["mcp", "list"])
    assert result.exit_code == 0
    assert "mcp:demo" in result.stdout
    assert "mcp_demo_echo" in result.stdout


def test_metrics_command_still_runs_without_data(monkeypatch, tmp_path):
    cfgmod._config = None
    monkeypatch.setenv("COURSE_AGENT_METRICS_DB", str(tmp_path / "metrics.db"))
    result = runner.invoke(app, ["metrics"])
    assert result.exit_code == 0
