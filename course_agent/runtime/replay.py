"""Task 015：replay artifact 的读写与展示."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from course_agent.graph.trace import ensure_trace_dir, summarize_text


def save_replay_artifact(
    artifact: dict[str, Any],
    *,
    trace_dir: str | Path,
) -> Path:
    """把 replay artifact 持久化为 JSON 文件."""
    base = ensure_trace_dir(trace_dir)
    thread_id = str(artifact.get("thread_id") or uuid4())
    path = base / f"{thread_id}.json"
    path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def load_replay_artifact(path: str | Path) -> dict[str, Any]:
    """读取 replay artifact."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def latest_replay_path(trace_dir: str | Path) -> Path | None:
    """返回最新的 replay 文件路径."""
    base = ensure_trace_dir(trace_dir)
    files = sorted(base.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def artifact_to_markdown(artifact: dict[str, Any]) -> str:
    """把 replay artifact 转成便于阅读的 Markdown."""
    lines = [
        f"# Replay · {artifact.get('runtime_kind', 'unknown')}",
        "",
        f"- thread_id: `{artifact.get('thread_id', '-')}`",
        f"- backend: `{artifact.get('backend', '-')}`",
        f"- steps: `{artifact.get('steps', '-')}`",
        f"- input: {summarize_text(artifact.get('input', ''), limit=200)}",
        "",
        "## Trace",
    ]
    for idx, item in enumerate(artifact.get("trace", []), 1):
        lines.append(
            f"{idx}. `{item.get('node', '-')}` / `{item.get('kind', '-')}`: "
            f"{item.get('summary', '')}"
        )
    lines.extend(
        [
            "",
            "## Final",
            "",
            artifact.get("final_answer", ""),
        ]
    )
    return "\n".join(lines)


def export_replay_markdown(
    artifact: dict[str, Any],
    *,
    trace_dir: str | Path,
) -> Path:
    """导出 replay 的 Markdown 版本."""
    base = ensure_trace_dir(trace_dir)
    thread_id = str(artifact.get("thread_id") or uuid4())
    path = base / f"{thread_id}.md"
    path.write_text(artifact_to_markdown(artifact), encoding="utf-8")
    return path


__all__ = [
    "artifact_to_markdown",
    "export_replay_markdown",
    "latest_replay_path",
    "load_replay_artifact",
    "save_replay_artifact",
]
