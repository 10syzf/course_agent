"""SolverAgent（Task 012）.

任务执行员：接收 PlannerAgent 拆出的单个 sub-task，执行并产出结果。

设计要点：
- 全工具集（与默认 ReAct AgentLoop 一致）—— Solver 是"动手干活"的角色
- 薄壳：核心还是复用 ``AgentLoop``，仅做 sub_task → prompt 的拼装
- 接收 dict 形式 sub_task（``{id, title, expected_output, suggested_tools}``）
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from course_agent.capabilities.adapters import (
    build_capability_tool_registry,
    build_default_capability_registry,
)
from course_agent.capabilities.registry import CapabilityRegistry
from course_agent.capabilities.router import CapabilityRouter
from course_agent.context.handoff import HandoffContext, SubTaskBrief
from course_agent.core.agent_loop import AgentLoop, AgentResult
from course_agent.core.state import AgentCallbacks
from course_agent.llm.base import BaseLLM, LLMMessage, StreamChunk
from course_agent.mcp.config import MCPConfig
from course_agent.observability.metrics import set_current_agent
from course_agent.tools.registry import ToolRegistry, get_registry

SOLVER_SYSTEM_PROMPT = """你是 Course Agent 的 Solver——任务执行员。
你会收到一个具体的 sub-task，包含 title / expected_output / suggested_tools。
你的职责：
1. 仔细阅读 sub-task 的 expected_output，明确产出标准
2. 必要时调用工具完成任务（suggested_tools 仅供参考，不是强制）
3. 直接给出**满足 expected_output**的最终结果，不要复述任务

【风格要求】
- 中文回复，简洁不啰嗦
- 代码用 ```python ``` 包裹；公式用 $...$ LaTeX
- 不要重复输出系统提示，不要"我将为你完成…"这种废话开头
"""


def _build_sub_task_prompt(sub_task: dict[str, Any]) -> str:
    """把 sub_task dict 拼成 Solver 能理解的用户提示."""
    sid = sub_task.get("id", "?")
    title = sub_task.get("title", "")
    expected = sub_task.get("expected_output", "")
    suggested = sub_task.get("suggested_tools") or []
    suggested_line = ", ".join(suggested) if suggested else "（无建议，自行选择）"
    return (
        f"# Sub-Task #{sid}\n"
        f"**标题**：{title}\n"
        f"**预期产出**：{expected}\n"
        f"**推荐工具**（仅供参考）：{suggested_line}\n\n"
        "请执行并直接给出最终结果。"
    )


def _append_handoff_prompt(prompt: str, handoff: HandoffContext | None) -> str:
    if handoff is None:
        return prompt
    lines = ["", "## 补充上下文"]
    if handoff.prior_subtask_summaries:
        lines.append("### 已完成子任务摘要")
        lines.extend(f"- {item}" for item in handoff.prior_subtask_summaries)
    if handoff.critic_feedback:
        lines.append("### 上一轮 Critic 意见")
        lines.append(handoff.critic_feedback)
    if handoff.pinned_facts:
        lines.append("### 必须保留的事实")
        lines.extend(f"- {item}" for item in handoff.pinned_facts)
    if handoff.refine_round:
        lines.append(f"### 当前 refine 轮次\n- 第 {handoff.refine_round} 轮")
    return prompt + "\n".join(lines)


class SolverAgent:
    """任务执行员 Agent：全工具集 + 薄壳 ReAct."""

    name = "Solver"

    def __init__(
        self,
        llm: BaseLLM,
        registry: ToolRegistry | None = None,
        max_steps: int = 8,
        system_prompt: str | None = None,
        capability_registry: CapabilityRegistry | None = None,
        capability_router: CapabilityRouter | None = None,
        mcp_cfg: MCPConfig | None = None,
        enable_capabilities: bool = False,
    ) -> None:
        reg = registry or get_registry()
        self.base_registry = reg
        self.capability_registry = capability_registry
        self.capability_router = capability_router

        if enable_capabilities:
            cap_registry = capability_registry or build_default_capability_registry(
                tool_registry=reg,
                mcp_cfg=mcp_cfg,
            )
            router = capability_router or CapabilityRouter(cap_registry)
            selected = router.select_for_agent("Solver")
            runtime_registry = build_capability_tool_registry(cap_registry, selected)
            self.allowed_tools = runtime_registry.list_names()
        else:
            runtime_registry = reg
            self.allowed_tools = reg.list_names()

        self.loop = AgentLoop(
            llm=llm,
            registry=runtime_registry,
            max_steps=max_steps,
            system_prompt=system_prompt or SOLVER_SYSTEM_PROMPT,
            prompt_role="solver",
        )

    @property
    def llm(self) -> BaseLLM:
        return self.loop.llm

    async def solve(
        self,
        sub_task: dict[str, Any],
        history: list[LLMMessage] | None = None,
        callbacks: AgentCallbacks | None = None,
        handoff: HandoffContext | None = None,
    ) -> AgentResult:
        """执行单个 sub_task；返回 AgentResult."""
        brief = SubTaskBrief.from_sub_task(sub_task)
        prompt = _append_handoff_prompt(_build_sub_task_prompt(brief.sub_task), handoff)
        token = set_current_agent(self.name)
        try:
            return await self.loop.arun(
                user_input=prompt,
                history=history,
                callbacks=callbacks,
                task_notes=handoff.to_task_notes() if handoff is not None else None,
            )
        finally:
            from course_agent.observability.metrics import _CURRENT_AGENT
            _CURRENT_AGENT.reset(token)

    async def arun(
        self,
        user_input: str,
        history: list[LLMMessage] | None = None,
        callbacks: AgentCallbacks | None = None,
    ) -> AgentResult:
        return await self.loop.arun(
            user_input=user_input, history=history, callbacks=callbacks
        )

    def astream_run(
        self,
        user_input: str,
        history: list[LLMMessage] | None = None,
        callbacks: AgentCallbacks | None = None,
    ) -> AsyncIterator[StreamChunk]:
        return self.loop.astream_run(
            user_input=user_input, history=history, callbacks=callbacks
        )

    def __repr__(self) -> str:
        return f"SolverAgent(tools={len(self.allowed_tools)}个, max_steps={self.loop.max_steps})"


__all__ = ["SolverAgent", "SOLVER_SYSTEM_PROMPT", "_append_handoff_prompt", "_build_sub_task_prompt"]
