"""Task 014：LangGraph Orchestrator 条件边."""

from __future__ import annotations

from course_agent.runtime.state import GraphRuntimeState


def after_pick_next(state: GraphRuntimeState) -> str:
    """决定下一步是执行 sub-task 还是结束."""
    return "solver" if state.get("current_sub_task") else "finalize"


def after_refine_decision(state: GraphRuntimeState) -> str:
    """决定是继续 refine 还是落盘当前 sub-task 结果."""
    return "solver" if state.get("should_retry") else "append_result"


__all__ = ["after_pick_next", "after_refine_decision"]
