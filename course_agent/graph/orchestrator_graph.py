"""Task 014：LangGraph 版 Orchestrator 图构建."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from course_agent.agent import Orchestrator
from course_agent.graph.edges import after_pick_next, after_refine_decision
from course_agent.graph.nodes import (
    append_result_node,
    critic_node,
    finalize_node,
    pick_next_subtask_node,
    planner_node,
    refine_decision_node,
    solver_node,
)
from course_agent.graph.prompts import GRAPH_FALLBACK_MERMAID
from course_agent.runtime.state import GraphRuntimeState


def build_orchestrator_graph(
    orchestrator: Orchestrator,
    *,
    callbacks_getter: Callable[[], Any | None] | None = None,
    checkpointer: Any | None = None,
):
    """构建 LangGraph Orchestrator."""

    callbacks_getter = callbacks_getter or (lambda: None)
    graph = StateGraph(GraphRuntimeState)

    async def _planner(state: GraphRuntimeState) -> dict[str, Any]:
        return await planner_node(state, orchestrator)

    def _pick_next(state: GraphRuntimeState) -> dict[str, Any]:
        return pick_next_subtask_node(state)

    async def _solver(state: GraphRuntimeState) -> dict[str, Any]:
        return await solver_node(
            state,
            orchestrator,
            callbacks=callbacks_getter(),
        )

    async def _critic(state: GraphRuntimeState) -> dict[str, Any]:
        return await critic_node(state, orchestrator)

    def _refine_decision(state: GraphRuntimeState) -> dict[str, Any]:
        return refine_decision_node(state, orchestrator)

    def _append_result(state: GraphRuntimeState) -> dict[str, Any]:
        return append_result_node(state)

    def _finalize(state: GraphRuntimeState) -> dict[str, Any]:
        return finalize_node(state, orchestrator)

    graph.add_node("planner", _planner)
    graph.add_node("pick_next_subtask", _pick_next)
    graph.add_node("solver", _solver)
    graph.add_node("critic", _critic)
    graph.add_node("refine_decision", _refine_decision)
    graph.add_node("append_result", _append_result)
    graph.add_node("finalize", _finalize)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "pick_next_subtask")
    graph.add_conditional_edges(
        "pick_next_subtask",
        after_pick_next,
        {
            "solver": "solver",
            "finalize": "finalize",
        },
    )
    graph.add_edge("solver", "critic")
    graph.add_edge("critic", "refine_decision")
    graph.add_conditional_edges(
        "refine_decision",
        after_refine_decision,
        {
            "solver": "solver",
            "append_result": "append_result",
        },
    )
    graph.add_edge("append_result", "pick_next_subtask")
    graph.add_edge("finalize", END)

    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()


def draw_mermaid(compiled_graph: Any) -> str:
    """尽量导出 Mermaid；失败则回退到静态文本."""
    try:
        return compiled_graph.get_graph().draw_mermaid()
    except Exception:
        return GRAPH_FALLBACK_MERMAID


__all__ = ["build_orchestrator_graph", "draw_mermaid"]
