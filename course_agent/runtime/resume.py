"""Task 016：resume 辅助函数."""

from __future__ import annotations

from course_agent.session import SessionStatus, TaskSession


def can_resume(session: TaskSession) -> bool:
    """当前 session 是否可以直接 resume."""
    return session.status == SessionStatus.WAITING_APPROVAL


def needs_human_input(session: TaskSession) -> bool:
    """当前 session 是否必须先补充人工输入."""
    return session.status == SessionStatus.WAITING_HUMAN_INPUT


__all__ = ["can_resume", "needs_human_input"]
