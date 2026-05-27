"""Task 014：metrics runtime_backend 维度测试."""

from __future__ import annotations

import pytest

from course_agent.observability.metrics import (
    MetricRecord,
    _insert,
    aggregate_by_agent,
    load_recent,
    reset_current_runtime_backend,
    set_current_runtime_backend,
    track_llm_call,
)


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    db_file = tmp_path / "metrics.db"
    monkeypatch.setenv("COURSE_AGENT_METRICS_DB", str(db_file))
    return db_file


def test_track_llm_call_uses_runtime_backend_contextvar(isolated_db):
    tok = set_current_runtime_backend("langgraph")
    try:
        with track_llm_call(agent_name="UnitAgent", model="mock-x"):
            pass
    finally:
        reset_current_runtime_backend(tok)
    rows = load_recent(10)
    assert any(r["runtime_backend"] == "langgraph" for r in rows)


def test_aggregate_by_agent_groups_by_backend(isolated_db):
    _insert(MetricRecord(agent_name="A", runtime_backend="legacy", model="m"))
    _insert(MetricRecord(agent_name="A", runtime_backend="langgraph", model="m"))
    agg = aggregate_by_agent(10)
    pairs = {(row["agent_name"], row["runtime_backend"]) for row in agg}
    assert ("A", "legacy") in pairs
    assert ("A", "langgraph") in pairs


def test_aggregate_by_agent_defaults_missing_backend_to_legacy(isolated_db):
    _insert(MetricRecord(agent_name="A", model="m"))
    agg = aggregate_by_agent(10)
    assert agg[0]["runtime_backend"] == "legacy"


def test_set_current_runtime_backend_roundtrip():
    tok = set_current_runtime_backend("langgraph")
    try:
        from course_agent.observability.metrics import get_current_runtime_backend

        assert get_current_runtime_backend() == "langgraph"
    finally:
        reset_current_runtime_backend(tok)
