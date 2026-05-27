"""Task 016：Session 状态模型."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class SessionStatus(StrEnum):
    """任务会话状态."""

    CREATED = "created"
    RUNNING = "running"
    WAITING_HUMAN_INPUT = "waiting_human_input"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def utc_now_iso() -> str:
    """返回当前 UTC 时间字符串."""
    return datetime.now(tz=UTC).isoformat()


class TaskSession(BaseModel):
    """Task 016：统一任务会话对象."""

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    runtime_kind: str = "react_graph"
    backend: str = "langgraph"
    status: SessionStatus = SessionStatus.CREATED
    input: str
    latest_answer: str | None = None
    latest_replay_path: str | None = None
    checkpoint_ref: str | None = None
    waiting_reason: str | None = None
    latest_human_input: str | None = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def touch(self) -> None:
        """刷新 updated_at."""
        self.updated_at = utc_now_iso()

    def set_status(self, status: SessionStatus, *, waiting_reason: str | None = None) -> None:
        """更新状态与等待原因."""
        self.status = status
        self.waiting_reason = waiting_reason
        self.touch()

    @property
    def is_waiting(self) -> bool:
        """当前是否处于等待人工状态."""
        return self.status in {
            SessionStatus.WAITING_HUMAN_INPUT,
            SessionStatus.WAITING_APPROVAL,
        }


__all__ = ["SessionStatus", "TaskSession", "utc_now_iso"]
