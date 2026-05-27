"""Task 015：benchmark CLI 测试."""

from __future__ import annotations

from typer.testing import CliRunner

from course_agent import config as cfgmod
from course_agent.cli import app

runner = CliRunner()


def test_benchmark_runtime_langgraph_runs():
    cfgmod._config = None
    result = runner.invoke(app, ["benchmark", "runtime", "--backend", "langgraph"])
    assert result.exit_code == 0
    assert "Benchmark" in result.stdout


def test_benchmark_runtime_legacy_runs():
    cfgmod._config = None
    result = runner.invoke(app, ["benchmark", "runtime", "--backend", "legacy"])
    assert result.exit_code == 0
    assert "legacy" in result.stdout


def test_benchmark_compare_runs():
    cfgmod._config = None
    result = runner.invoke(app, ["benchmark", "compare"])
    assert result.exit_code == 0
    assert "Runtime Compare" in result.stdout
    assert "langgraph" in result.stdout
    assert "legacy" in result.stdout


def test_benchmark_compare_accepts_custom_query():
    cfgmod._config = None
    result = runner.invoke(app, ["benchmark", "compare", "--query", "你好"])
    assert result.exit_code == 0


def test_benchmark_runtime_outputs_runtime_kind():
    cfgmod._config = None
    result = runner.invoke(app, ["benchmark", "runtime", "--backend", "langgraph"])
    assert result.exit_code == 0
    assert "runtime_kind" in result.stdout
