"""Task 015：trace schema 测试."""

from __future__ import annotations

from course_agent.graph.trace import (
    append_graph_trace,
    build_replay_artifact,
    summarize_text,
    trace_nodes,
)


def test_summarize_text_truncates_long_content():
    text = "a" * 300
    out = summarize_text(text, limit=50)
    assert len(out) == 50
    assert out.endswith("...")


def test_append_graph_trace_appends_entry():
    rows = append_graph_trace([], node="llm", kind="model_call", summary="hello")
    assert rows[0]["node"] == "llm"
    assert rows[0]["kind"] == "model_call"
    assert "ts" in rows[0]


def test_trace_nodes_extracts_sequence():
    seq = trace_nodes(
        [
            {"node": "prepare_context"},
            {"node": "llm"},
            {"node": "tool"},
            {"node": "llm"},
        ]
    )
    assert seq == ["prepare_context", "llm", "tool", "llm"]


def test_build_replay_artifact_contains_required_fields():
    artifact = build_replay_artifact(
        query="你好",
        backend="langgraph",
        runtime_kind="react_graph",
        final_answer="done",
        steps=2,
        trace=[{"node": "llm", "kind": "final_answer", "summary": "done"}],
    )
    assert artifact["backend"] == "langgraph"
    assert artifact["runtime_kind"] == "react_graph"
    assert artifact["steps"] == 2
    assert artifact["node_sequence"] == ["llm"]
