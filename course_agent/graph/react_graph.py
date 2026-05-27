"""Task 015：Graph-native ReAct 图构建."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from course_agent.graph.human_nodes import (
    decide_human_gate,
    wait_approval_node,
    wait_human_input_node,
)
from course_agent.graph.react_nodes import (
    finalize_node,
    llm_node,
    prepare_context_node,
    tool_node,
)
from course_agent.graph.trace import append_graph_trace
from course_agent.tools.registry import ToolRegistry


class ReactGraphState(TypedDict, total=False):
    """Graph-native ReAct 运行时状态."""

    user_input: str
    messages: list[dict[str, Any]]
    pending_tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    final_answer: str
    steps: int
    max_steps: int
    backend: str
    runtime_kind: str
    trace: list[dict[str, Any]]
    done: bool
    status: str
    waiting_reason: str
    session_id: str
    resume_input: str


def make_initial_react_state(
    user_input: str,
    *,
    messages: list[dict[str, Any]],
    max_steps: int,
    backend: str = "langgraph",
    session_id: str | None = None,
    resume_input: str | None = None,
) -> ReactGraphState:
    """构造 react graph 初始状态."""
    return ReactGraphState(
        user_input=user_input,
        messages=messages,
        pending_tool_calls=[],
        tool_results=[],
        final_answer="",
        steps=0,
        max_steps=max_steps,
        backend=backend,
        runtime_kind="react_graph",
        status="running",
        waiting_reason="",
        session_id=session_id or "",
        resume_input=resume_input or "",
        trace=append_graph_trace(
            [],
            node="start",
            kind="input",
            summary=user_input[:160],
        ),
        done=False,
    )


def build_react_graph(
    *,
    llm: Any,
    registry: ToolRegistry,
    tool_schemas: list[dict[str, Any]],
    callbacks_getter: Callable[[], Any | None] | None = None,
):
    """构建 graph-native ReAct 图."""
    callbacks_getter = callbacks_getter or (lambda: None)
    graph = StateGraph(ReactGraphState)

    async def _prepare_context(state: ReactGraphState) -> dict[str, Any]:
        return await prepare_context_node(state)

    async def _llm(state: ReactGraphState) -> dict[str, Any]:
        return await llm_node(
            state,
            llm=llm,
            tool_schemas=tool_schemas,
            callbacks=callbacks_getter(),
        )

    async def _tool(state: ReactGraphState) -> dict[str, Any]:
        return await tool_node(
            state,
            registry=registry,
            callbacks=callbacks_getter(),
        )

    async def _finalize(state: ReactGraphState) -> dict[str, Any]:
        return await finalize_node(state)

    async def _wait_human_input(state: ReactGraphState) -> dict[str, Any]:
        return await wait_human_input_node(state)

    async def _wait_approval(state: ReactGraphState) -> dict[str, Any]:
        return await wait_approval_node(state)

    graph.add_node("prepare_context", _prepare_context)
    graph.add_node("wait_human_input", _wait_human_input)
    graph.add_node("wait_approval", _wait_approval)
    graph.add_node("llm", _llm)
    graph.add_node("tool", _tool)
    graph.add_node("finalize", _finalize)

    graph.add_edge(START, "prepare_context")
    graph.add_conditional_edges(
        "prepare_context",
        decide_human_gate,
        {
            "llm": "llm",
            "wait_human_input": "wait_human_input",
            "wait_approval": "wait_approval",
        },
    )
    graph.add_conditional_edges(
        "llm",
        _after_llm,
        {
            "tool": "tool",
            "finalize": "finalize",
        },
    )
    graph.add_conditional_edges(
        "tool",
        _after_tool,
        {
            "llm": "llm",
            "finalize": "finalize",
        },
    )
    graph.add_edge("finalize", END)
    graph.add_edge("wait_human_input", END)
    graph.add_edge("wait_approval", END)
    return graph.compile()


def _after_llm(state: ReactGraphState) -> str:
    if state.get("done"):
        return "finalize"
    if state.get("pending_tool_calls"):
        return "tool"
    return "finalize"


def _after_tool(state: ReactGraphState) -> str:
    if int(state.get("steps", 0)) >= int(state.get("max_steps", 0)):
        return "finalize"
    return "llm"


def draw_react_mermaid(compiled_graph: Any) -> str:
    """导出 ReAct graph 的 Mermaid 文本."""
    try:
        return compiled_graph.get_graph().draw_mermaid()
    except Exception:
        return """flowchart TD
    START([START]) --> PrepareContext
    PrepareContext --> LLM
    LLM -->|tool_calls| Tool
    Tool --> LLM
    LLM -->|final| Finalize
    Finalize --> END([END])
"""


__all__ = [
    "ReactGraphState",
    "build_react_graph",
    "draw_react_mermaid",
    "make_initial_react_state",
]
