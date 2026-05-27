"""Task 016：session CLI 测试."""

from __future__ import annotations

from typer.testing import CliRunner

from course_agent import config as cfgmod
from course_agent.cli import app

runner = CliRunner()


def _set_env(monkeypatch, tmp_path):
    cfgmod._config = None
    monkeypatch.setenv("RUNTIME_SESSION_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("RUNTIME_TRACE_DIR", str(tmp_path / "replays"))


def _extract_session_id(output: str) -> str:
    for line in output.splitlines():
        if "session_id=" in line:
            part = line.split("session_id=", 1)[1].strip()
            return part.split()[0]
    raise AssertionError("session_id not found")


def test_session_start_creates_session(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    result = runner.invoke(app, ["session", "start", "你好"])
    assert result.exit_code == 0
    assert "Session Detail" in result.stdout


def test_session_list_shows_created_session(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    runner.invoke(app, ["session", "start", "你好"])
    result = runner.invoke(app, ["session", "list"])
    assert result.exit_code == 0
    assert "Sessions" in result.stdout


def test_session_show_displays_session_detail(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    started = runner.invoke(app, ["session", "start", "你好"])
    session_id = _extract_session_id(started.stdout)
    result = runner.invoke(app, ["session", "show", session_id])
    assert result.exit_code == 0
    assert session_id in result.stdout


def test_session_resume_waiting_approval(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    started = runner.invoke(app, ["session", "start", "这个任务需要你确认后再继续"])
    session_id = _extract_session_id(started.stdout)
    result = runner.invoke(app, ["session", "resume", session_id])
    assert result.exit_code == 0
    assert "completed" in result.stdout


def test_session_continue_waiting_human_input(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    started = runner.invoke(app, ["session", "start", "这题我稍后补充资料"])
    session_id = _extract_session_id(started.stdout)
    result = runner.invoke(
        app,
        ["session", "continue", session_id, "--input", "补充信息：继续"],
    )
    assert result.exit_code == 0
    assert "completed" in result.stdout


def test_session_cancel_updates_status(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    started = runner.invoke(app, ["session", "start", "你好"])
    session_id = _extract_session_id(started.stdout)
    result = runner.invoke(app, ["session", "cancel", session_id])
    assert result.exit_code == 0
    assert "cancelled" in result.stdout
