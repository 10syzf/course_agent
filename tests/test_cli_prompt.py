"""Task 017：prompt CLI 测试."""

from __future__ import annotations

from typer.testing import CliRunner

from course_agent import config as cfgmod
from course_agent.cli import app

runner = CliRunner()


def _set_env(monkeypatch, tmp_path):
    cfgmod._config = None
    monkeypatch.setenv("RUNTIME_PROMPT_DIR", str(tmp_path))


def test_prompt_inspect_runs(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    result = runner.invoke(app, ["prompt", "inspect"])
    assert result.exit_code == 0
    assert "Prompt Inspect" in result.stdout


def test_prompt_inspect_accepts_role_and_query(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    result = runner.invoke(
        app,
        ["prompt", "inspect", "--role", "solver", "--query", "帮我算 1+1"],
    )
    assert result.exit_code == 0
    assert "Static Prefix" in result.stdout


def test_prompt_latest_reads_latest_artifact(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    runner.invoke(app, ["prompt", "inspect"])
    result = runner.invoke(app, ["prompt", "latest"])
    assert result.exit_code == 0
    assert "# Prompt Inspect" in result.stdout


def test_prompt_profile_runs(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    result = runner.invoke(app, ["prompt", "profile"])
    assert result.exit_code == 0
    assert "Prompt Profile" in result.stdout


def test_prompt_latest_without_artifact_exits_nonzero(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    result = runner.invoke(app, ["prompt", "latest"])
    assert result.exit_code == 1
