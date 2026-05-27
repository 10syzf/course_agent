"""Task 016：session 模型测试."""

from __future__ import annotations

from course_agent.session.models import SessionStatus, TaskSession


def test_task_session_defaults_are_initialized():
    session = TaskSession(title="demo", input="hello")
    assert session.session_id
    assert session.status == SessionStatus.CREATED
    assert session.runtime_kind == "react_graph"


def test_task_session_touch_updates_timestamp():
    session = TaskSession(title="demo", input="hello")
    before = session.updated_at
    session.touch()
    assert session.updated_at >= before


def test_task_session_set_status_updates_waiting_reason():
    session = TaskSession(title="demo", input="hello")
    session.set_status(
        SessionStatus.WAITING_HUMAN_INPUT,
        waiting_reason="need more context",
    )
    assert session.status == SessionStatus.WAITING_HUMAN_INPUT
    assert session.waiting_reason == "need more context"


def test_task_session_is_waiting_only_for_waiting_states():
    waiting = TaskSession(title="demo", input="hello")
    waiting.set_status(SessionStatus.WAITING_APPROVAL)
    done = TaskSession(title="done", input="hello")
    done.set_status(SessionStatus.COMPLETED)
    assert waiting.is_waiting is True
    assert done.is_waiting is False
