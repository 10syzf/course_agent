"""Task 014：CLI runtime / graph 测试."""

from __future__ import annotations

from typer.testing import CliRunner

from course_agent import config as cfgmod
from course_agent.cli import app

runner = CliRunner()


def test_runtime_command_shows_current_backend():
    cfgmod._config = None
    result = runner.invoke(app, ["runtime"])
    assert result.exit_code == 0
    assert "backend=" in result.stdout
    assert "checkpoint=" in result.stdout


def test_runtime_command_backend_override():
    cfgmod._config = None
    result = runner.invoke(app, ["runtime", "--backend", "legacy"])
    assert result.exit_code == 0
    assert "backend=legacy" in result.stdout


def test_runtime_command_backend_override_langgraph():
    cfgmod._config = None
    result = runner.invoke(app, ["runtime", "--backend", "langgraph"])
    assert result.exit_code == 0
    assert "backend=langgraph" in result.stdout


def test_graph_command_exports_langgraph_mermaid():
    cfgmod._config = None
    result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert "graph TD" in result.stdout or "flowchart TD" in result.stdout


def test_graph_command_can_export_legacy_graph():
    cfgmod._config = None
    result = runner.invoke(app, ["graph", "--backend", "legacy"])
    assert result.exit_code == 0
    assert "Planner" in result.stdout
