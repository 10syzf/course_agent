from __future__ import annotations

from typer.testing import CliRunner

from course_agent import config as cfgmod
from course_agent.cli import app

runner = CliRunner()


def _set_env(monkeypatch, tmp_path):
    cfgmod._config = None
    monkeypatch.setenv('RUNTIME_CONTEXT_DIR', str(tmp_path))


def test_context_inspect_runs(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    result = runner.invoke(app, ['context', 'inspect'])
    assert result.exit_code == 0
    assert 'Context Inspect' in result.stdout


def test_context_inspect_accepts_role_and_query(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    result = runner.invoke(app, ['context', 'inspect', '--role', 'solver', '--query', '帮我总结'])
    assert result.exit_code == 0
    assert '# Context Inspect' in result.stdout


def test_context_latest_reads_latest_artifact(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    runner.invoke(app, ['context', 'inspect'])
    result = runner.invoke(app, ['context', 'latest'])
    assert result.exit_code == 0
    assert '# Context Inspect' in result.stdout


def test_context_profile_runs(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    result = runner.invoke(app, ['context', 'profile'])
    assert result.exit_code == 0
    assert 'Context Profile' in result.stdout


def test_context_latest_without_artifact_exits_nonzero(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    result = runner.invoke(app, ['context', 'latest'])
    assert result.exit_code == 1
