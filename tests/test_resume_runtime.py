"""Task 016：resume runtime 测试."""

from __future__ import annotations

import pytest

from course_agent.llm import MockLLM
from course_agent.runtime.react_graph_runtime import ReactGraphRuntime
from course_agent.runtime.resume import can_resume, needs_human_input
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
async def test_session_runtime_start_waiting_human_input(tmp_path):
    runtime = _runtime(tmp_path)
    result = await runtime.start("这题我稍后补充资料")
    assert result.session.status == SessionStatus.WAITING_HUMAN_INPUT


@pytest.mark.asyncio
async def test_session_runtime_start_waiting_approval(tmp_path):
    runtime = _runtime(tmp_path)
    result = await runtime.start("这个任务需要你确认后再继续")
    assert result.session.status == SessionStatus.WAITING_APPROVAL


@pytest.mark.asyncio
async def test_session_runtime_continue_waiting_human_input_to_completed(tmp_path):
    runtime = _runtime(tmp_path)
    first = await runtime.start("这题我稍后补充资料")
    second = await runtime.continue_session(first.session.session_id, "补充信息：请直接回答")
    assert second.session.status == SessionStatus.COMPLETED
    assert second.runtime_result.answer


@pytest.mark.asyncio
async def test_session_runtime_resume_waiting_approval_to_completed(tmp_path):
    runtime = _runtime(tmp_path)
    first = await runtime.start("这个任务需要你确认后再继续")
    second = await runtime.resume(first.session.session_id)
    assert second.session.status == SessionStatus.COMPLETED


def test_resume_helpers_match_session_status(tmp_path):
    runtime = _runtime(tmp_path)
    session = runtime.manager.create_session(title="demo", user_input="hello")
    runtime.manager.mark_waiting_approval(session.session_id, waiting_reason="need approval")
    approval = runtime.get_session(session.session_id)
    assert approval is not None
    assert can_resume(approval) is True
    assert needs_human_input(approval) is False
