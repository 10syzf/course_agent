"""Observability metrics 单测（Task 012）.

覆盖：
- ensure_schema 建表 + 幂等
- track_llm_call 正常路径：计时 + 落库 + status=ok
- track_llm_call 异常路径：status=error / error 字段有内容 / 原异常继续抛
- contextvar set_current_agent / get_current_agent
- aggregate_by_agent 按 Agent 汇总 tokens + 平均时延 + 错误率
- course-agent metrics CLI 不崩（空表 + 有数据）
"""

from __future__ import annotations

import sqlite3

import pytest
from typer.testing import CliRunner

from course_agent.cli import app
from course_agent.observability.metrics import (
    MetricRecord,
    _insert,
    aggregate_by_agent,
    ensure_schema,
    get_current_agent,
    get_db_path,
    load_recent,
    set_current_agent,
    track_llm_call,
)

runner = CliRunner()


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    db_file = tmp_path / "metrics.db"
    monkeypatch.setenv("COURSE_AGENT_METRICS_DB", str(db_file))
    return db_file


def test_ensure_schema_creates_table_idempotent(isolated_db):
    p1 = ensure_schema()
    p2 = ensure_schema()
    assert p1 == p2 == get_db_path()
    # Schema 可查
    with sqlite3.connect(str(p1)) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='metrics'"
        ).fetchall()
        assert rows


def test_set_and_get_current_agent():
    tok = set_current_agent("TestAgent")
    try:
        assert get_current_agent() == "TestAgent"
    finally:
        from course_agent.observability.metrics import _CURRENT_AGENT

        _CURRENT_AGENT.reset(tok)


def test_track_llm_call_happy_path_inserts_row(isolated_db):
    with track_llm_call(agent_name="UnitAgent", model="mock-x") as rec:
        rec.prompt_tokens = 10
        rec.completion_tokens = 20
    rows = load_recent(10)
    assert any(
        r["agent_name"] == "UnitAgent"
        and r["model"] == "mock-x"
        and r["prompt_tokens"] == 10
        and r["completion_tokens"] == 20
        and r["status"] == "ok"
        for r in rows
    )


def test_track_llm_call_exception_records_error_and_reraises(isolated_db):
    with pytest.raises(ValueError, match="boom"):
        with track_llm_call(agent_name="FailAgent", model="m"):
            raise ValueError("boom")
    rows = load_recent(10)
    err_rows = [r for r in rows if r["agent_name"] == "FailAgent"]
    assert err_rows
    assert err_rows[0]["status"] == "error"
    assert "ValueError" in (err_rows[0]["error"] or "")


def test_track_llm_call_uses_contextvar_when_no_agent_name(isolated_db):
    tok = set_current_agent("CtxAgent")
    try:
        with track_llm_call(model="m"):
            pass
    finally:
        from course_agent.observability.metrics import _CURRENT_AGENT

        _CURRENT_AGENT.reset(tok)
    rows = load_recent(10)
    assert any(r["agent_name"] == "CtxAgent" for r in rows)


def test_aggregate_by_agent_groups_and_computes(isolated_db):
    _insert(
        MetricRecord(
            agent_name="A", model="m", prompt_tokens=100, completion_tokens=50,
            latency_ms=200, status="ok",
        )
    )
    _insert(
        MetricRecord(
            agent_name="A", model="m", prompt_tokens=50, completion_tokens=25,
            latency_ms=400, status="error", error="oops",
        )
    )
    _insert(
        MetricRecord(
            agent_name="B", model="m", prompt_tokens=10, completion_tokens=5,
            latency_ms=100, status="ok",
        )
    )
    agg = aggregate_by_agent(50)
    by_name = {a["agent_name"]: a for a in agg}
    assert by_name["A"]["calls"] == 2
    assert by_name["A"]["prompt_tokens"] == 150
    assert by_name["A"]["completion_tokens"] == 75
    assert by_name["A"]["avg_latency_ms"] == 300
    assert abs(by_name["A"]["error_rate"] - 0.5) < 1e-6
    assert by_name["B"]["calls"] == 1


def test_metrics_cli_empty_does_not_crash(isolated_db):
    result = runner.invoke(app, ["metrics"])
    assert result.exit_code == 0
    assert "暂无" in result.stdout or "Metrics" in result.stdout


def test_metrics_cli_with_data_shows_table(isolated_db):
    _insert(
        MetricRecord(
            agent_name="Planner", model="m", prompt_tokens=100,
            completion_tokens=50, latency_ms=123, status="ok",
        )
    )
    result = runner.invoke(app, ["metrics", "--raw"])
    assert result.exit_code == 0
    assert "Planner" in result.stdout
