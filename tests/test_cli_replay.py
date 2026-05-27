"""Task 015：replay CLI 测试."""

from __future__ import annotations

from typer.testing import CliRunner

from course_agent import config as cfgmod
from course_agent.cli import app
from course_agent.runtime.replay import save_replay_artifact

runner = CliRunner()


def _artifact() -> dict:
    return {
        "thread_id": "cli-replay",
        "backend": "langgraph",
        "runtime_kind": "react_graph",
        "input": "帮我算 1+1",
        "steps": 2,
        "trace": [{"node": "llm", "kind": "final_answer", "summary": "2"}],
        "final_answer": "2",
        "final_answer_summary": "2",
    }


def test_replay_latest_shows_latest_file(monkeypatch, tmp_path):
    cfgmod._config = None
    save_replay_artifact(_artifact(), trace_dir=tmp_path)
    monkeypatch.setenv("RUNTIME_TRACE_DIR", str(tmp_path))
    result = runner.invoke(app, ["replay", "latest"])
    assert result.exit_code == 0
    assert "Latest Replay" in result.stdout


def test_replay_show_renders_markdown(tmp_path):
    path = save_replay_artifact(_artifact(), trace_dir=tmp_path)
    result = runner.invoke(app, ["replay", "show", str(path)])
    assert result.exit_code == 0
    assert "Replay" in result.stdout


def test_replay_export_md_outputs_path(monkeypatch, tmp_path):
    cfgmod._config = None
    save_replay_artifact(_artifact(), trace_dir=tmp_path)
    monkeypatch.setenv("RUNTIME_TRACE_DIR", str(tmp_path))
    result = runner.invoke(app, ["replay", "export", "--format", "md"])
    assert result.exit_code == 0
    assert ".md" in result.stdout


def test_replay_latest_without_file_exits_nonzero(monkeypatch, tmp_path):
    cfgmod._config = None
    monkeypatch.setenv("RUNTIME_TRACE_DIR", str(tmp_path))
    result = runner.invoke(app, ["replay", "latest"])
    assert result.exit_code == 1
