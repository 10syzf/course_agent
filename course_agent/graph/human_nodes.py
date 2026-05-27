"""Task 016：Human-in-the-loop 节点."""

from __future__ import annotations

from typing import Any

from course_agent.graph.trace import append_graph_trace

_WAIT_HUMAN_INPUT_HINTS = (
    "补充",
    "补充资料",
    "补充信息",
    "我稍后补充",
    "等我补充",
    "缺少资料",
)
_WAIT_APPROVAL_HINTS = (
    "确认后再继续",
    "需要你确认",
    "批准后继续",
    "approval",
)


def decide_human_gate(state: dict[str, Any]) -> str:
    """决定是否进入人工输入 / 审批等待节点."""
    if state.get("resume_input"):
        return "llm"
    user_input = str(state.get("user_input", ""))
    if any(token in user_input for token in _WAIT_APPROVAL_HINTS):
        return "wait_approval"
    if any(token in user_input for token in _WAIT_HUMAN_INPUT_HINTS):
        return "wait_human_input"
    return "llm"


async def wait_human_input_node(state: dict[str, Any]) -> dict[str, Any]:
    """进入等待人工补充输入状态."""
    reason = "缺少关键上下文，请补充后继续该任务。"
    return {
        "done": True,
        "status": "waiting_human_input",
        "waiting_reason": reason,
        "final_answer": reason,
        "trace": append_graph_trace(
            state.get("trace", []),
            node="wait_human_input",
            kind="pause",
            summary=reason,
        ),
    }


async def wait_approval_node(state: dict[str, Any]) -> dict[str, Any]:
    """进入等待人工审批状态."""
    reason = "任务已暂停，等待你确认后继续。"
    return {
        "done": True,
        "status": "waiting_approval",
        "waiting_reason": reason,
        "final_answer": reason,
        "trace": append_graph_trace(
            state.get("trace", []),
            node="wait_approval",
            kind="pause",
            summary=reason,
        ),
    }


__all__ = ["decide_human_gate", "wait_approval_node", "wait_human_input_node"]
