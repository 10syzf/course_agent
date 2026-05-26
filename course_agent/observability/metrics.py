"""LLM 调用可观测面板（Task 012）.

把每次 LLM 调用的 ``(agent_name, model, prompt_tokens, completion_tokens, latency_ms,
status, error)`` 落到 SQLite，便于：
- ``course-agent metrics`` 命令表格化展示
- 多 Agent 编排时定位 token 大头是哪个角色

设计要点：
- **`contextvar` 传递 ``CURRENT_AGENT``**：异步安全，跟着 task 走；
  Agent 入口处 ``set_current_agent("Planner")``，结束 reset
- **失败不影响主流程**：metrics 写入异常只 log warning
- **DB 路径**：``~/.cache/course-agent/metrics.db``（与已有 ``data/`` 区分，这是工具自身缓存）
"""

from __future__ import annotations

import contextvars
import os
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from course_agent.logger import get_logger

_log = get_logger("metrics")

_DB_PATH_ENV = "COURSE_AGENT_METRICS_DB"
_DEFAULT_DB_PATH = Path("~/.cache/course-agent/metrics.db").expanduser()

# contextvar：跨 async task 透传 "当前 Agent 名"
_CURRENT_AGENT: contextvars.ContextVar[str] = contextvars.ContextVar(
    "course_agent_current_agent", default="ReAct"
)


def get_db_path() -> Path:
    p = os.getenv(_DB_PATH_ENV)
    if p:
        return Path(p).expanduser()
    return _DEFAULT_DB_PATH


def ensure_schema() -> Path:
    """确保 metrics.db 存在且 schema 就绪；返回 db 路径."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                agent_name TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                latency_ms INTEGER DEFAULT 0,
                status TEXT DEFAULT 'ok',
                error TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS capability_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                capability_name TEXT NOT NULL,
                capability_kind TEXT NOT NULL,
                provider_name TEXT NOT NULL,
                latency_ms INTEGER DEFAULT 0,
                status TEXT DEFAULT 'ok',
                error TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(ts DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cap_metrics_ts ON capability_metrics(ts DESC)"
        )
    return db_path


def set_current_agent(name: str) -> contextvars.Token:
    """设置当前 Agent 名（返回的 token 可用于后续 reset）."""
    return _CURRENT_AGENT.set(name)


def get_current_agent() -> str:
    return _CURRENT_AGENT.get()


@dataclass
class MetricRecord:
    """一次 LLM 调用的 metric."""

    agent_name: str = ""
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    status: str = "ok"
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CapabilityMetricRecord:
    """一次 capability 调用的 metric."""

    capability_name: str = ""
    capability_kind: str = ""
    provider_name: str = ""
    latency_ms: int = 0
    status: str = "ok"
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _insert(rec: MetricRecord) -> None:
    try:
        db_path = ensure_schema()
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                """
                INSERT INTO metrics
                  (ts, agent_name, model, prompt_tokens, completion_tokens,
                   latency_ms, status, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    time.time(),
                    rec.agent_name,
                    rec.model,
                    int(rec.prompt_tokens or 0),
                    int(rec.completion_tokens or 0),
                    int(rec.latency_ms or 0),
                    rec.status,
                    rec.error,
                ),
            )
    except Exception as e:  # noqa: BLE001  metrics 失败不能影响主流程
        _log.warning(f"metrics 写入失败：{type(e).__name__}: {e}")


def _insert_capability(rec: CapabilityMetricRecord) -> None:
    try:
        db_path = ensure_schema()
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                """
                INSERT INTO capability_metrics
                  (ts, capability_name, capability_kind, provider_name,
                   latency_ms, status, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    time.time(),
                    rec.capability_name,
                    rec.capability_kind,
                    rec.provider_name,
                    int(rec.latency_ms or 0),
                    rec.status,
                    rec.error,
                ),
            )
    except Exception as e:  # noqa: BLE001
        _log.warning(f"capability metrics 写入失败：{type(e).__name__}: {e}")


@contextmanager
def track_llm_call(agent_name: str | None = None, model: str = ""):
    """LLM 调用计时 + 落库的上下文管理器.

    用法::

        with track_llm_call(model="qwen-plus") as rec:
            resp = client.chat.completions.create(...)
            rec.prompt_tokens = resp.usage.prompt_tokens
            rec.completion_tokens = resp.usage.completion_tokens

    若不传 ``agent_name`` 则从 contextvar 读 ``CURRENT_AGENT``。
    异常会被记录但**继续抛出**（不吞错）。
    """
    rec = MetricRecord(
        agent_name=agent_name or get_current_agent(),
        model=model,
        status="ok",
    )
    t0 = time.perf_counter()
    try:
        yield rec
    except Exception as e:  # noqa: BLE001
        rec.status = "error"
        rec.error = f"{type(e).__name__}: {str(e)[:300]}"
        rec.latency_ms = int((time.perf_counter() - t0) * 1000)
        _insert(rec)
        raise
    else:
        rec.latency_ms = int((time.perf_counter() - t0) * 1000)
        _insert(rec)


@contextmanager
def track_capability_call(
    capability_name: str,
    capability_kind: str,
    provider_name: str,
):
    """Capability 调用计时 + 落库."""
    rec = CapabilityMetricRecord(
        capability_name=capability_name,
        capability_kind=capability_kind,
        provider_name=provider_name,
        status="ok",
    )
    t0 = time.perf_counter()
    try:
        yield rec
    except Exception as e:  # noqa: BLE001
        rec.status = "error"
        rec.error = f"{type(e).__name__}: {str(e)[:300]}"
        rec.latency_ms = int((time.perf_counter() - t0) * 1000)
        _insert_capability(rec)
        raise
    else:
        rec.latency_ms = int((time.perf_counter() - t0) * 1000)
        _insert_capability(rec)


def load_recent(limit: int = 50) -> list[dict[str, Any]]:
    """读最近 N 条 metrics（按 ts 倒序）."""
    try:
        db_path = ensure_schema()
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM metrics ORDER BY ts DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:  # noqa: BLE001
        _log.warning(f"metrics 读取失败：{type(e).__name__}: {e}")
        return []


def load_recent_capabilities(limit: int = 50) -> list[dict[str, Any]]:
    """读最近 N 条 capability metrics（按 ts 倒序）."""
    try:
        db_path = ensure_schema()
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM capability_metrics ORDER BY ts DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:  # noqa: BLE001
        _log.warning(f"capability metrics 读取失败：{type(e).__name__}: {e}")
        return []


def aggregate_by_agent(limit: int = 50) -> list[dict[str, Any]]:
    """对最近 N 条 metrics 按 agent_name 聚合：调用数 / token 总和 / 平均时延 / 错误率."""
    rows = load_recent(limit)
    if not rows:
        return []
    bucket: dict[str, dict[str, Any]] = {}
    for r in rows:
        a = r["agent_name"] or "unknown"
        b = bucket.setdefault(
            a,
            {
                "agent_name": a,
                "calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "latency_total_ms": 0,
                "errors": 0,
            },
        )
        b["calls"] += 1
        b["prompt_tokens"] += int(r.get("prompt_tokens") or 0)
        b["completion_tokens"] += int(r.get("completion_tokens") or 0)
        b["latency_total_ms"] += int(r.get("latency_ms") or 0)
        if r.get("status") == "error":
            b["errors"] += 1
    out = []
    for b in bucket.values():
        avg_latency = (
            b["latency_total_ms"] // b["calls"] if b["calls"] else 0
        )
        err_rate = (b["errors"] / b["calls"]) if b["calls"] else 0.0
        out.append(
            {
                "agent_name": b["agent_name"],
                "calls": b["calls"],
                "prompt_tokens": b["prompt_tokens"],
                "completion_tokens": b["completion_tokens"],
                "avg_latency_ms": avg_latency,
                "error_rate": err_rate,
            }
        )
    out.sort(key=lambda x: x["calls"], reverse=True)
    return out


def aggregate_capabilities(limit: int = 50) -> list[dict[str, Any]]:
    """按 capability 聚合最近 N 条调用记录."""
    rows = load_recent_capabilities(limit)
    if not rows:
        return []
    bucket: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        key = (r["capability_name"], r["capability_kind"])
        b = bucket.setdefault(
            key,
            {
                "capability_name": r["capability_name"],
                "capability_kind": r["capability_kind"],
                "provider_name": r["provider_name"],
                "calls": 0,
                "latency_total_ms": 0,
                "errors": 0,
            },
        )
        b["calls"] += 1
        b["latency_total_ms"] += int(r.get("latency_ms") or 0)
        if r.get("status") == "error":
            b["errors"] += 1
    out = []
    for b in bucket.values():
        out.append(
            {
                "capability_name": b["capability_name"],
                "capability_kind": b["capability_kind"],
                "provider_name": b["provider_name"],
                "calls": b["calls"],
                "avg_latency_ms": (
                    b["latency_total_ms"] // b["calls"] if b["calls"] else 0
                ),
                "error_rate": (b["errors"] / b["calls"]) if b["calls"] else 0.0,
            }
        )
    out.sort(key=lambda x: x["calls"], reverse=True)
    return out


__all__ = [
    "CapabilityMetricRecord",
    "MetricRecord",
    "aggregate_by_agent",
    "aggregate_capabilities",
    "ensure_schema",
    "get_current_agent",
    "get_db_path",
    "load_recent",
    "load_recent_capabilities",
    "set_current_agent",
    "track_capability_call",
    "track_llm_call",
]
