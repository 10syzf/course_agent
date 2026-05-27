"""Task 015：runtime benchmark / compare."""

from __future__ import annotations

import time
from typing import Any

from course_agent.runtime import create_chat_runtime


def run_runtime_benchmark(
    cfg: Any,
    *,
    backend: str,
    query: str,
    llm: Any | None = None,
    registry: Any | None = None,
) -> dict[str, Any]:
    """运行一次单 Agent runtime benchmark."""
    runtime = create_chat_runtime(
        cfg,
        llm=llm,
        registry=registry,
        backend=backend,
    )
    t0 = time.perf_counter()
    result = runtime.run(query)
    latency_ms = int((time.perf_counter() - t0) * 1000)
    trace = list(getattr(result, "trace", []))
    return {
        "backend": backend,
        "runtime_kind": getattr(result, "runtime_kind", "legacy_react"),
        "latency_ms": latency_ms,
        "steps": int(getattr(result, "steps", 0)),
        "tool_calls": len([t for t in trace if t.get("kind") == "tool_call"]),
        "node_count": len(trace),
        "answer": getattr(result, "answer", ""),
        "replay_path": getattr(result, "replay_path", None),
    }


def compare_runtime_benchmarks(
    cfg: Any,
    *,
    query: str,
    llm: Any | None = None,
    registry: Any | None = None,
) -> list[dict[str, Any]]:
    """对比 legacy 与 langgraph 两种 chat runtime."""
    return [
        run_runtime_benchmark(
            cfg,
            backend="legacy",
            query=query,
            llm=llm,
            registry=registry,
        ),
        run_runtime_benchmark(
            cfg,
            backend="langgraph",
            query=query,
            llm=llm,
            registry=registry,
        ),
    ]


__all__ = ["compare_runtime_benchmarks", "run_runtime_benchmark"]
