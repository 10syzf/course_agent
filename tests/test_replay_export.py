"""Task 015：replay artifact 导出测试."""

from __future__ import annotations

from course_agent.runtime.replay import (
    artifact_to_markdown,
    export_replay_markdown,
    latest_replay_path,
    load_replay_artifact,
    save_replay_artifact,
)


def _artifact() -> dict:
    return {
        "thread_id": "abc123",
        "backend": "langgraph",
        "runtime_kind": "react_graph",
        "input": "帮我算 1+1",
        "steps": 2,
        "trace": [
            {"node": "prepare_context", "kind": "context", "summary": "messages=2"},
            {"node": "llm", "kind": "final_answer", "summary": "2"},
        ],
        "final_answer": "2",
        "final_answer_summary": "2",
    }


def test_save_and_load_replay_artifact(tmp_path):
    path = save_replay_artifact(_artifact(), trace_dir=tmp_path)
    data = load_replay_artifact(path)
    assert data["thread_id"] == "abc123"
    assert data["final_answer"] == "2"


def test_latest_replay_path_returns_newest(tmp_path):
    p1 = save_replay_artifact({**_artifact(), "thread_id": "a"}, trace_dir=tmp_path)
    p2 = save_replay_artifact({**_artifact(), "thread_id": "b"}, trace_dir=tmp_path)
    assert latest_replay_path(tmp_path) == p2
    assert p1.exists()


def test_artifact_to_markdown_contains_trace_and_final():
    md = artifact_to_markdown(_artifact())
    assert "# Replay" in md
    assert "prepare_context" in md
    assert "## Final" in md


def test_export_replay_markdown_writes_md_file(tmp_path):
    path = export_replay_markdown(_artifact(), trace_dir=tmp_path)
    assert path.suffix == ".md"
    assert "Replay" in path.read_text(encoding="utf-8")


def test_latest_replay_path_returns_none_when_empty(tmp_path):
    assert latest_replay_path(tmp_path) is None
