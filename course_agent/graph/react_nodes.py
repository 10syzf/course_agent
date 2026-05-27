"""Task 015：Graph-native ReAct 节点实现."""

from __future__ import annotations

import asyncio
from typing import Any

from course_agent.graph.trace import append_graph_trace, summarize_text
from course_agent.llm.base import BaseLLM, LLMMessage
from course_agent.tools.registry import ToolRegistry


async def prepare_context_node(state: dict[str, Any]) -> dict[str, Any]:
    """初始化或补全消息上下文."""
    messages = list(state.get("messages", []))
    return {
        "messages": messages,
        "trace": append_graph_trace(
            state.get("trace", []),
            node="prepare_context",
            kind="context",
            summary=f"messages={len(messages)}",
        ),
    }


async def llm_node(
    state: dict[str, Any],
    *,
    llm: BaseLLM,
    tool_schemas: list[dict[str, Any]],
    callbacks: Any | None = None,
) -> dict[str, Any]:
    """调用 LLM，决定是继续 tool loop 还是结束."""
    step = int(state.get("steps", 0)) + 1
    messages = [
        LLMMessage.model_validate(item)
        for item in state.get("messages", [])
    ]
    response = await llm.achat(messages=messages, tools=tool_schemas)

    out_messages = list(state.get("messages", []))
    pending_tool_calls: list[dict[str, Any]] = []
    trace = list(state.get("trace", []))
    final_answer = state.get("final_answer", "")
    done = False

    if response.tool_calls:
        out_messages.append(
            LLMMessage(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls,
            ).model_dump()
        )
        pending_tool_calls = [tc.model_dump() for tc in response.tool_calls]
        trace = append_graph_trace(
            trace,
            node="llm",
            kind="tool_plan",
            summary=summarize_text(response.content or "(no thought)"),
            data={"tool_calls": pending_tool_calls},
        )
        if callbacks is not None and hasattr(callbacks, "on_thought"):
            await callbacks.on_thought(step, response.content or "")
    else:
        final_answer = response.content or ""
        out_messages.append(
            LLMMessage(role="assistant", content=final_answer).model_dump()
        )
        trace = append_graph_trace(
            trace,
            node="llm",
            kind="final_answer",
            summary=summarize_text(final_answer),
        )
        done = True
        if callbacks is not None and hasattr(callbacks, "on_final"):
            await callbacks.on_final(final_answer)

    return {
        "steps": step,
        "messages": out_messages,
        "pending_tool_calls": pending_tool_calls,
        "final_answer": final_answer,
        "done": done,
        "trace": trace,
    }


async def tool_node(
    state: dict[str, Any],
    *,
    registry: ToolRegistry,
    callbacks: Any | None = None,
) -> dict[str, Any]:
    """执行当前 LLM 规划出的工具调用."""
    messages = list(state.get("messages", []))
    trace = list(state.get("trace", []))
    results: list[dict[str, Any]] = []
    for call in state.get("pending_tool_calls", []):
        name = str(call.get("name", ""))
        arguments = dict(call.get("arguments", {}) or {})
        if callbacks is not None and hasattr(callbacks, "on_tool_call"):
            await callbacks.on_tool_call(int(state.get("steps", 0)), name, arguments)
        trace = append_graph_trace(
            trace,
            node="tool",
            kind="tool_call",
            summary=name,
            data=arguments,
        )
        is_error = False
        try:
            tool = registry.get(name)
            result = await asyncio.to_thread(tool.run, **arguments)
        except Exception as e:  # noqa: BLE001
            result = f"[工具 {name} 执行异常] {e}"
            is_error = True
        result_str = str(result)
        messages.append(
            LLMMessage(
                role="tool",
                name=name,
                tool_call_id=str(call.get("id", "")),
                content=result_str,
            ).model_dump()
        )
        results.append({"name": name, "result": result_str, "is_error": is_error})
        trace = append_graph_trace(
            trace,
            node="tool",
            kind="tool_result",
            summary=summarize_text(result_str),
            data={"name": name, "is_error": is_error},
        )
        if callbacks is not None and hasattr(callbacks, "on_tool_result"):
            await callbacks.on_tool_result(
                int(state.get("steps", 0)),
                name,
                result_str,
                is_error,
            )
    return {
        "messages": messages,
        "pending_tool_calls": [],
        "tool_results": list(state.get("tool_results", [])) + results,
        "trace": trace,
    }


async def finalize_node(state: dict[str, Any]) -> dict[str, Any]:
    """收尾；若尚无最终答案则给出超步数提示."""
    final_answer = str(state.get("final_answer") or "")
    if not final_answer:
        final_answer = (
            f"[已达最大步数 {state.get('max_steps', '?')}，任务未完成] "
            f"最近一次状态：{state.get('messages', [])[-1].get('content', '') if state.get('messages') else ''}"
        )
    return {
        "done": True,
        "final_answer": final_answer,
        "trace": append_graph_trace(
            state.get("trace", []),
            node="finalize",
            kind="finalize",
            summary=summarize_text(final_answer),
        ),
    }


__all__ = [
    "finalize_node",
    "llm_node",
    "prepare_context_node",
    "tool_node",
]
