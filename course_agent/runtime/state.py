"""Task 014：LangGraph 运行时状态模型."""

from __future__ import annotations

from typing import Any, TypedDict

from course_agent.agent import OrchestratorResult, SubTaskResult
from course_agent.llm.base import LLMMessage


class GraphRuntimeState(TypedDict, total=False):
    """LangGraph 节点之间传递的状态."""

    user_task: str
    plan: list[dict[str, Any]]
    current_index: int
    current_sub_task: dict[str, Any] | None
    solver_output: str
    critic_result: dict[str, Any]
    sub_results: list[dict[str, Any]]
    refine_round: int
    should_retry: bool
    total_llm_calls: int
    final_answer: str
    backend: str
    trace: list[dict[str, Any]]
    accumulated_history: list[dict[str, Any]]


def make_initial_state(
    user_task: str,
    *,
    backend: str = "langgraph",
) -> GraphRuntimeState:
    """构造图运行时的初始状态."""
    return GraphRuntimeState(
        user_task=user_task,
        plan=[],
        current_index=0,
        current_sub_task=None,
        solver_output="",
        critic_result={},
        sub_results=[],
        refine_round=0,
        should_retry=False,
        total_llm_calls=0,
        final_answer="",
        backend=backend,
        trace=[],
        accumulated_history=[],
    )


def history_from_state(state: GraphRuntimeState) -> list[LLMMessage]:
    """把状态里的 history dict 还原为 LLMMessage."""
    return [
        LLMMessage.model_validate(item)
        for item in state.get("accumulated_history", [])
    ]


def append_trace(
    state: GraphRuntimeState,
    *,
    node: str,
    detail: str,
    extra: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """追加一条轻量 trace 记录."""
    trace = list(state.get("trace", []))
    payload = {"node": node, "detail": detail}
    if extra:
        payload.update(extra)
    trace.append(payload)
    return trace


def state_to_result(state: GraphRuntimeState) -> OrchestratorResult:
    """把 graph state 还原成 OrchestratorResult."""
    return OrchestratorResult(
        final_answer=state.get("final_answer", ""),
        plan=state.get("plan", []),
        sub_results=[
            SubTaskResult.model_validate(item)
            for item in state.get("sub_results", [])
        ],
        total_llm_calls=state.get("total_llm_calls", 0),
    )


__all__ = [
    "GraphRuntimeState",
    "append_trace",
    "history_from_state",
    "make_initial_state",
    "state_to_result",
]
