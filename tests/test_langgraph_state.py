"""Task 014：GraphRuntimeState 单测."""

from __future__ import annotations

from course_agent.runtime.state import (
    append_trace,
    history_from_state,
    make_initial_state,
    state_to_result,
)


def test_make_initial_state_sets_defaults():
    state = make_initial_state("写一个线代复习计划", backend="langgraph")
    assert state["user_task"] == "写一个线代复习计划"
    assert state["backend"] == "langgraph"
    assert state["plan"] == []
    assert state["sub_results"] == []
    assert state["total_llm_calls"] == 0
    assert state["should_retry"] is False


def test_make_initial_state_uses_default_backend():
    state = make_initial_state("hello")
    assert state["backend"] == "langgraph"


def test_history_from_state_returns_llm_messages():
    state = make_initial_state("x")
    state["accumulated_history"] = [
        {"role": "system", "content": "s"},
        {"role": "assistant", "content": "a"},
    ]
    history = history_from_state(state)
    assert [m.role for m in history] == ["system", "assistant"]
    assert [m.content for m in history] == ["s", "a"]


def test_history_from_state_empty_when_missing():
    history = history_from_state(make_initial_state("x"))
    assert history == []


def test_append_trace_appends_without_mutating_old_list():
    state = make_initial_state("x")
    trace1 = append_trace(state, node="planner", detail="planned")
    trace2 = append_trace({**state, "trace": trace1}, node="solver", detail="solved")
    assert len(trace1) == 1
    assert len(trace2) == 2
    assert trace2[1]["node"] == "solver"


def test_append_trace_keeps_extra_payload():
    state = make_initial_state("x")
    trace = append_trace(state, node="critic", detail="checked", extra={"score": 4})
    assert trace[0]["score"] == 4


def test_state_to_result_restores_sub_results():
    state = make_initial_state("x")
    state["plan"] = [{"id": 1, "title": "A"}]
    state["sub_results"] = [
        {
            "sub_task": {"id": 1, "title": "A"},
            "solver_output": "done",
            "critic": {"score": 4, "pass": True, "feedback": "ok"},
            "refine_rounds": 1,
        }
    ]
    state["final_answer"] = "final"
    state["total_llm_calls"] = 3
    result = state_to_result(state)
    assert result.final_answer == "final"
    assert result.total_llm_calls == 3
    assert result.sub_results[0].solver_output == "done"
    assert result.sub_results[0].refine_rounds == 1
