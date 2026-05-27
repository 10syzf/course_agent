"""Task 016：Stateful session runtime."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from course_agent.runtime.react_graph_runtime import (
    ReactGraphResult,
    ReactGraphRuntime,
)
from course_agent.session import SessionManager, SessionStatus, SessionStore, TaskSession


class SessionRunResult(BaseModel):
    """一次 session 运行结果."""

    session: TaskSession
    runtime_result: ReactGraphResult


class SessionRuntime:
    """把 graph runtime 升级为有状态任务执行器."""

    def __init__(
        self,
        *,
        runtime: ReactGraphRuntime,
        session_store: SessionStore,
    ) -> None:
        self.runtime = runtime
        self.store = session_store
        self.manager = SessionManager(session_store)

    def list_sessions(self) -> list[TaskSession]:
        return self.manager.list_sessions()

    def get_session(self, session_id: str) -> TaskSession | None:
        return self.manager.get(session_id)

    async def start(
        self,
        query: str,
        *,
        title: str | None = None,
        history: list[Any] | None = None,
        callbacks: Any | None = None,
    ) -> SessionRunResult:
        session = self.manager.create_session(
            title=title or _make_title(query),
            user_input=query,
            runtime_kind=self.runtime.runtime_kind,
            backend=self.runtime.backend,
        )
        return await self._run_session(session, history=history, callbacks=callbacks)

    async def resume(
        self,
        session_id: str,
        *,
        callbacks: Any | None = None,
    ) -> SessionRunResult:
        session = self._require(session_id)
        if session.status != SessionStatus.WAITING_APPROVAL:
            raise ValueError("只有 waiting_approval 状态才能直接 resume")
        self.manager.attach_human_input(session_id, "approved")
        return await self._run_session(
            session,
            resume_input="approved",
            callbacks=callbacks,
        )

    async def continue_session(
        self,
        session_id: str,
        user_input: str,
        *,
        callbacks: Any | None = None,
    ) -> SessionRunResult:
        session = self._require(session_id)
        self.manager.attach_human_input(session_id, user_input)
        return await self._run_session(
            session,
            resume_input=user_input,
            callbacks=callbacks,
        )

    def cancel(self, session_id: str) -> TaskSession:
        return self.manager.mark_cancelled(session_id)

    async def _run_session(
        self,
        session: TaskSession,
        *,
        history: list[Any] | None = None,
        callbacks: Any | None = None,
        resume_input: str | None = None,
    ) -> SessionRunResult:
        self.manager.mark_running(session.session_id)
        try:
            result = await self.runtime.arun(
                session.input,
                history=history,
                callbacks=callbacks,
                session_id=session.session_id,
                resume_input=resume_input,
            )
        except Exception as e:  # noqa: BLE001
            latest = self.manager.mark_failed(session.session_id, reason=str(e))
            raise RuntimeError(latest.latest_answer or str(e)) from e

        if result.status == "waiting_human_input":
            latest = self.manager.mark_waiting_human_input(
                session.session_id,
                waiting_reason=result.waiting_reason or "等待补充信息",
                latest_replay_path=result.replay_path,
            )
        elif result.status == "waiting_approval":
            latest = self.manager.mark_waiting_approval(
                session.session_id,
                waiting_reason=result.waiting_reason or "等待审批",
                latest_replay_path=result.replay_path,
            )
        else:
            latest = self.manager.mark_completed(
                session.session_id,
                answer=result.answer,
                replay_path=result.replay_path,
            )
        return SessionRunResult(session=latest, runtime_result=result)

    def _require(self, session_id: str) -> TaskSession:
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(f"session not found: {session_id}")
        return session


def _make_title(query: str) -> str:
    query = query.strip().replace("\n", " ")
    return query[:40] if len(query) > 40 else query


__all__ = ["SessionRunResult", "SessionRuntime"]
