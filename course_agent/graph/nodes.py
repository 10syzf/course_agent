"""Task 014：LangGraph Orchestrator 节点实现."""

from __future__ import annotations

from typing import Any

from course_agent.agent import Orchestrator
from course_agent.llm.base import LLMMessage
from course_agent.runtime.state import (
    GraphRuntimeState,
    append_trace,
    history_from_state,
)


async def planner_node(
    state: GraphRuntimeState,
    orchestrator: Orchestrator,
) -> dict[str, Any]:
    """规划原始任务."""
    plan = await orchestrator.planner.plan(state["user_task"])
    total_calls = state.get("total_llm_calls", 0) + 1
    return {
        "plan": plan[: orchestrator.max_sub_tasks],
        "current_index": 0,
        "sub_results": [],
        "refine_round": 0,
        "total_llm_calls": total_calls,
        "trace": append_trace(
            state,
            node="planner",
            detail=f"planned {len(plan[: orchestrator.max_sub_tasks])} sub-tasks",
        ),
    }


def pick_next_subtask_node(state: GraphRuntimeState) -> dict[str, Any]:
    """选择下一个待处理 sub-task."""
    plan = state.get("plan", [])
    index = state.get("current_index", 0)
    current = plan[index] if index < len(plan) else None
    detail = (
        f"picked sub-task #{current.get('id', index + 1)}"
        if current
        else "no more sub-task"
    )
    return {
        "current_sub_task": current,
        "solver_output": "",
        "critic_result": {},
        "refine_round": 0,
        "should_retry": False,
        "trace": append_trace(state, node="pick_next", detail=detail),
    }


async def solver_node(
    state: GraphRuntimeState,
    orchestrator: Orchestrator,
    callbacks: Any | None = None,
) -> dict[str, Any]:
    """执行当前 sub-task."""
    sub_task = state.get("current_sub_task")
    if not sub_task:
        return {}

    total_calls = state.get("total_llm_calls", 0)
    if total_calls >= orchestrator.max_total_llm_calls:
        raise RuntimeError(
            f"Orchestrator 总 LLM 调用数已达上限 "
            f"{orchestrator.max_total_llm_calls}，强制中止以防死循环"
        )

    history = history_from_state(state)
    solver_result = await orchestrator.solver.solve(
        sub_task,
        history=history if history else None,
        callbacks=callbacks,
    )
    total_calls += 1
    return {
        "solver_output": solver_result.answer,
        "total_llm_calls": total_calls,
        "trace": append_trace(
            state,
            node="solver",
            detail=f"solved sub-task #{sub_task.get('id', '?')}",
            extra={"refine_round": state.get("refine_round", 0)},
        ),
    }


async def critic_node(
    state: GraphRuntimeState,
    orchestrator: Orchestrator,
) -> dict[str, Any]:
    """评审当前 sub-task 结果."""
    sub_task = state.get("current_sub_task")
    if not sub_task:
        return {}

    total_calls = state.get("total_llm_calls", 0)
    if total_calls >= orchestrator.max_total_llm_calls:
        critic_result = {
            "score": 3,
            "pass": True,
            "feedback": "⚠️ 已达 LLM 调用上限，跳过 Critic",
        }
        return {
            "critic_result": critic_result,
            "trace": append_trace(
                state,
                node="critic",
                detail="skipped because llm budget reached",
            ),
        }

    critic_result = await orchestrator.critic.critique(
        sub_task,
        state.get("solver_output", ""),
    )
    total_calls += 1
    return {
        "critic_result": critic_result,
        "total_llm_calls": total_calls,
        "trace": append_trace(
            state,
            node="critic",
            detail=(
                f"critic pass={critic_result.get('pass')} "
                f"score={critic_result.get('score')}"
            ),
        ),
    }


def refine_decision_node(
    state: GraphRuntimeState,
    orchestrator: Orchestrator,
) -> dict[str, Any]:
    """决定是否继续 refine."""
    critic_result = state.get("critic_result", {})
    current_sub_task = state.get("current_sub_task")
    if not current_sub_task:
        return {"refine_round": 0}

    if critic_result.get("pass"):
        return {
            "should_retry": False,
            "trace": append_trace(
                state,
                node="refine_decision",
                detail="critic passed, append result",
            ),
        }

    current_round = state.get("refine_round", 0)
    if current_round >= orchestrator.max_refine_per_task:
        return {
            "should_retry": False,
            "trace": append_trace(
                state,
                node="refine_decision",
                detail=(
                    "critic failed but refine limit reached, keep current result"
                ),
            ),
        }

    history = list(state.get("accumulated_history", []))
    history.append(
        LLMMessage(
            role="system",
            content=(
                f"[Critic Feedback for sub-task #{current_sub_task.get('id', '?')}] "
                f"{critic_result.get('feedback', '')}"
            ),
        ).model_dump()
    )
    return {
        "accumulated_history": history,
        "refine_round": current_round + 1,
        "should_retry": True,
        "trace": append_trace(
            state,
            node="refine_decision",
            detail="critic failed, retry solver",
            extra={"next_round": current_round + 1},
        ),
    }


def append_result_node(state: GraphRuntimeState) -> dict[str, Any]:
    """写入当前 sub-task 结果，并把摘要注入后续 history."""
    sub_task = state.get("current_sub_task")
    if not sub_task:
        return {}

    sub_results = list(state.get("sub_results", []))
    critic_result = state.get("critic_result", {})
    solver_output = state.get("solver_output", "")
    refine_rounds = state.get("refine_round", 0)
    sub_results.append(
        {
            "sub_task": sub_task,
            "solver_output": solver_output,
            "critic": critic_result,
            "refine_rounds": refine_rounds,
        }
    )

    history = list(state.get("accumulated_history", []))
    history.append(
        LLMMessage(
            role="assistant",
            content=(
                f"[Sub-Task #{sub_task.get('id', '?')} 完成] "
                f"{solver_output[:300]}"
                + ("..." if len(solver_output) > 300 else "")
            ),
        ).model_dump()
    )

    return {
        "sub_results": sub_results,
        "accumulated_history": history,
        "current_index": state.get("current_index", 0) + 1,
        "current_sub_task": None,
        "solver_output": "",
        "critic_result": {},
        "refine_round": 0,
        "should_retry": False,
        "trace": append_trace(
            state,
            node="append_result",
            detail=f"stored sub-task #{sub_task.get('id', '?')}",
        ),
    }


def finalize_node(
    state: GraphRuntimeState,
    orchestrator: Orchestrator,
) -> dict[str, Any]:
    """合成最终答案."""
    from course_agent.agent import SubTaskResult

    sub_results = [
        SubTaskResult.model_validate(item)
        for item in state.get("sub_results", [])
    ]
    final_answer = orchestrator._synthesize(state.get("plan", []), sub_results)
    return {
        "final_answer": final_answer,
        "trace": append_trace(
            state,
            node="finalize",
            detail=f"finalized with {len(sub_results)} sub-results",
        ),
    }


__all__ = [
    "append_result_node",
    "critic_node",
    "finalize_node",
    "pick_next_subtask_node",
    "planner_node",
    "refine_decision_node",
    "solver_node",
]
