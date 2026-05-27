"""Task 015：Graph trace / replay 结构化辅助函数."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def summarize_text(text: str | None, *, limit: int = 160) -> str:
    """压缩长文本，便于 trace / replay 展示."""
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def append_graph_trace(
    trace: list[dict[str, Any]],
    *,
    node: str,
    kind: str,
    summary: str,
    data: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """追加一条 graph trace，返回新列表."""
    rows = list(trace)
    item = {
        "node": node,
        "kind": kind,
        "summary": summary,
        "ts": datetime.now(tz=UTC).isoformat(),
    }
    if data:
        item["data"] = data
    rows.append(item)
    return rows


def trace_nodes(trace: list[dict[str, Any]]) -> list[str]:
    """提取按顺序出现过的节点名."""
    nodes: list[str] = []
    for item in trace:
        node = str(item.get("node", "")).strip()
        if node:
            nodes.append(node)
    return nodes


def build_replay_artifact(
    *,
    query: str,
    backend: str,
    runtime_kind: str,
    final_answer: str,
    steps: int,
    trace: list[dict[str, Any]],
    thread_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造统一 replay artifact."""
    artifact = {
        "thread_id": thread_id or str(uuid4()),
        "backend": backend,
        "runtime_kind": runtime_kind,
        "input": query,
        "steps": steps,
        "trace": trace,
        "node_sequence": trace_nodes(trace),
        "final_answer": final_answer,
        "final_answer_summary": summarize_text(final_answer, limit=240),
        "created_at": datetime.now(tz=UTC).isoformat(),
    }
    if extra:
        artifact["extra"] = extra
    return artifact


def ensure_trace_dir(trace_dir: str | Path) -> Path:
    path = Path(trace_dir).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


__all__ = [
    "append_graph_trace",
    "build_replay_artifact",
    "ensure_trace_dir",
    "summarize_text",
    "trace_nodes",
]
