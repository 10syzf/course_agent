"""Task 017：Prompt compiler 与 artifact."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from course_agent.graph.trace import ensure_trace_dir
from course_agent.prompt.dynamic_tail import build_dynamic_tail
from course_agent.prompt.models import PromptEnvelope, PromptSection
from course_agent.prompt.static_prefix import build_static_prefix


def compile_prompt(
    *,
    role: str,
    role_prompt: str = "",
    user_input: str,
    history_count: int = 0,
    project_root: str | Path | None = None,
    env_notes: str | dict[str, Any] | None = None,
    memory_notes: str | dict[str, Any] | None = None,
    mcp_notes: str | dict[str, Any] | None = None,
    session_notes: str | dict[str, Any] | None = None,
    task_notes: str | dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> PromptEnvelope:
    """编译 prompt，输出静态前缀与动态尾部."""
    static_prefix, static_sections = build_static_prefix(
        role=role,
        role_prompt=role_prompt,
    )
    dynamic_tail, dynamic_sections = build_dynamic_tail(
        user_input=user_input,
        history_count=history_count,
        project_root=project_root,
        env_notes=env_notes,
        memory_notes=memory_notes,
        mcp_notes=mcp_notes,
        session_notes=session_notes,
        task_notes=task_notes,
    )
    return PromptEnvelope.create(
        role=role,
        static_prefix=static_prefix,
        dynamic_tail=dynamic_tail,
        sections=[*static_sections, *dynamic_sections],
        metadata=metadata or {},
    )


def save_prompt_artifact(
    envelope: PromptEnvelope,
    *,
    prompt_dir: str | Path = "data/prompts",
    artifact_id: str | None = None,
) -> Path:
    """保存 prompt inspect artifact."""
    base = ensure_trace_dir(prompt_dir)
    path = base / f"{artifact_id or uuid4()}.json"
    path.write_text(
        json.dumps(envelope.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def latest_prompt_path(prompt_dir: str | Path = "data/prompts") -> Path | None:
    base = ensure_trace_dir(prompt_dir)
    files = sorted(base.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def load_prompt_artifact(path: str | Path) -> PromptEnvelope:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data["sections"] = [
        PromptSection.model_validate(item) for item in data.get("sections", [])
    ]
    return PromptEnvelope.model_validate(data)


def prompt_to_markdown(envelope: PromptEnvelope) -> str:
    """将 prompt artifact 转为 markdown."""
    lines = [
        f"# Prompt Inspect · {envelope.role}",
        "",
        f"- static_hash: `{envelope.static_hash}`",
        f"- dynamic_hash: `{envelope.dynamic_hash}`",
        "",
        "## Static Prefix",
        "",
        envelope.static_prefix,
        "",
        "## Dynamic Tail",
        "",
        envelope.dynamic_tail,
        "",
        "## Full Prompt",
        "",
        envelope.full_prompt,
    ]
    return "\n".join(lines)


__all__ = [
    "compile_prompt",
    "latest_prompt_path",
    "load_prompt_artifact",
    "prompt_to_markdown",
    "save_prompt_artifact",
]
