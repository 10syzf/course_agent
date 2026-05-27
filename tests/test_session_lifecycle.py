"""Task 016：session 生命周期测试."""

from __future__ import annotations

import pytest

from course_agent.llm import MockLLM
from course_agent.runtime.react_graph_runtime import ReactGraphRuntime
from course_agent.runtime.session_runtime import SessionRuntime
from course_agent.session import SessionStatus, SessionStore
from course_agent.tools import get_registry


def _runtime(tmp_path):
    return SessionRuntime(
        runtime=ReactGraphRuntime(
            llm=MockLLM(),
            registry=get_registry(),
            max_steps=4,
            trace_dir=str(tmp_path / "replays"),
        ),
        session_store=SessionStore(tmp_path / "sessions"),
    )


@pytest.mark.asyncio
async def test_session_lifecycle_created_to_completed(tmp_path):
    runtime = _runtime(tmp_path)
    result = await runtime.start("你好")
    assert result.session.status == SessionStatus.COMPLETED


@pytest.mark.asyncio
async def test_session_lifecycle_created_to_waiting_human_input(tmp_path):
    runtime = _runtime(tmp_path)
    result = await runtime.start("等我补充资料之后再继续")
    assert result.session.status == SessionStatus.WAITING_HUMAN_INPUT


@pytest.mark.asyncio
async def test_session_lifecycle_created_to_waiting_approval(tmp_path):
    runtime = _runtime(tmp_path)
    result = await runtime.start("需要你确认后再继续这个任务")
    assert result.session.status == SessionStatus.WAITING_APPROVAL


@pytest.mark.asyncio
async def test_session_lifecycle_waiting_to_completed_via_continue(tmp_path):
    runtime = _runtime(tmp_path)
    first = await runtime.start("等我补充资料之后再继续")
    second = await runtime.continue_session(first.session.session_id, "补充完了，继续")
    assert second.session.status == SessionStatus.COMPLETED


def test_session_lifecycle_cancelled(tmp_path):
    runtime = _runtime(tmp_path)
    created = runtime.manager.create_session(title="demo", user_input="hello")
    cancelled = runtime.cancel(created.session_id)
    assert cancelled.status == SessionStatus.CANCELLED
