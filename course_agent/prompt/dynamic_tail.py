"""Task 017：动态尾部构建."""

from __future__ import annotations

import platform
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from course_agent.prompt.models import PromptSection
from course_agent.prompt.project_instructions import find_project_root, read_project_instructions


def build_dynamic_tail(
    *,
    user_input: str,
    history_count: int = 0,
    project_root: str | Path | None = None,
    env_notes: str | dict[str, Any] | None = None,
    memory_notes: str | dict[str, Any] | None = None,
    mcp_notes: str | dict[str, Any] | None = None,
    session_notes: str | dict[str, Any] | None = None,
    task_notes: str | dict[str, Any] | None = None,
) -> tuple[str, list[PromptSection]]:
    """构建动态尾部."""
    root = find_project_root(project_root)
    sections: list[PromptSection] = []
    env_content = _build_env_content(root, env_notes)
    if env_content:
        sections.append(PromptSection(name="env_section", content=env_content, is_static=False))

    path, project_content = read_project_instructions(root)
    if project_content:
        sections.append(
            PromptSection(
                name="project_instruction_section",
                content=project_content,
                is_static=False,
                metadata={"path": str(path) if path else ""},
            )
        )

    for name, content in (
        ("memory_section", _render_notes(memory_notes)),
        ("mcp_section", _render_notes(mcp_notes)),
        ("session_section", _render_notes(session_notes)),
        ("task_context_section", _render_task_section(user_input, history_count, task_notes)),
    ):
        if content:
            sections.append(PromptSection(name=name, content=content, is_static=False))

    text = "\n\n".join(
        f"[{section.name}]\n{section.content}" for section in sections if section.content
    )
    return text.strip(), sections


def _build_env_content(root: Path, env_notes: str | dict[str, Any] | None) -> str:
    git_summary = _git_summary(root)
    parts = [
        f"工作目录: {root}",
        f"平台: {platform.system().lower()} ({platform.platform()})",
        f"Python: {platform.python_version()}",
        f"今日日期: {date.today().isoformat()}",
    ]
    if git_summary:
        parts.append(f"Git 状态: {git_summary}")
    extra = _render_notes(env_notes)
    if extra:
        parts.append(extra)
    return "\n".join(parts)


def _git_summary(root: Path) -> str:
    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return f"branch={branch or '-'}, commit={commit or '-'}"
    except Exception:
        return ""


def _render_notes(notes: str | dict[str, Any] | None) -> str:
    if notes is None:
        return ""
    if isinstance(notes, str):
        return notes.strip()
    lines = [f"- {key}: {value}" for key, value in notes.items()]
    return "\n".join(lines).strip()


def _render_task_section(
    user_input: str,
    history_count: int,
    task_notes: str | dict[str, Any] | None,
) -> str:
    parts = [
        f"用户输入: {user_input}",
        f"历史消息数: {history_count}",
    ]
    extra = _render_notes(task_notes)
    if extra:
        parts.append(extra)
    return "\n".join(parts)


__all__ = ["build_dynamic_tail"]
