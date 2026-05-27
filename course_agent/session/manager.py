"""Task 016：Session 管理器."""

from __future__ import annotations

from course_agent.session.models import SessionStatus, TaskSession
from course_agent.session.store import SessionStore


class SessionManager:
    """封装 TaskSession 的创建与状态流转."""

    def __init__(self, store: SessionStore) -> None:
        self.store = store

    def create_session(
        self,
        *,
        title: str,
        user_input: str,
        runtime_kind: str = "react_graph",
        backend: str = "langgraph",
    ) -> TaskSession:
        session = TaskSession(
            title=title,
            input=user_input,
            runtime_kind=runtime_kind,
            backend=backend,
        )
        return self.store.save_session(session)

    def get(self, session_id: str) -> TaskSession | None:
        return self.store.get_session(session_id)

    def list_sessions(self) -> list[TaskSession]:
        return self.store.list_sessions()

    def mark_running(self, session_id: str) -> TaskSession:
        session = self._require(session_id)
        session.set_status(SessionStatus.RUNNING)
        return self.store.save_session(session)

    def mark_waiting_human_input(
        self,
        session_id: str,
        *,
        waiting_reason: str,
        latest_replay_path: str | None = None,
    ) -> TaskSession:
        session = self._require(session_id)
        session.set_status(
            SessionStatus.WAITING_HUMAN_INPUT,
            waiting_reason=waiting_reason,
        )
        session.latest_replay_path = latest_replay_path
        session.checkpoint_ref = latest_replay_path
        return self.store.save_session(session)

    def mark_waiting_approval(
        self,
        session_id: str,
        *,
        waiting_reason: str,
        latest_replay_path: str | None = None,
    ) -> TaskSession:
        session = self._require(session_id)
        session.set_status(
            SessionStatus.WAITING_APPROVAL,
            waiting_reason=waiting_reason,
        )
        session.latest_replay_path = latest_replay_path
        session.checkpoint_ref = latest_replay_path
        return self.store.save_session(session)

    def mark_completed(
        self,
        session_id: str,
        *,
        answer: str,
        replay_path: str | None = None,
    ) -> TaskSession:
        session = self._require(session_id)
        session.latest_answer = answer
        session.latest_replay_path = replay_path
        session.checkpoint_ref = replay_path
        session.set_status(SessionStatus.COMPLETED)
        return self.store.save_session(session)

    def mark_failed(self, session_id: str, *, reason: str) -> TaskSession:
        session = self._require(session_id)
        session.latest_answer = reason
        session.set_status(SessionStatus.FAILED, waiting_reason=reason)
        return self.store.save_session(session)

    def mark_cancelled(self, session_id: str) -> TaskSession:
        session = self._require(session_id)
        session.set_status(SessionStatus.CANCELLED)
        return self.store.save_session(session)

    def attach_human_input(self, session_id: str, user_input: str) -> TaskSession:
        session = self._require(session_id)
        session.latest_human_input = user_input
        session.touch()
        return self.store.save_session(session)

    def _require(self, session_id: str) -> TaskSession:
        session = self.store.get_session(session_id)
        if session is None:
            raise KeyError(f"session not found: {session_id}")
        return session


__all__ = ["SessionManager"]
