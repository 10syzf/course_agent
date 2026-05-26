"""Orchestrator（Task 012）.

编排 Plan → Solve → Critique → (Refine | Done) 闭环；本身**不调 LLM**，只编排。

硬上限（防 token 失控 / 死循环）：
- 全局 sub-task 数 ≤ ``max_sub_tasks``（默认 5）—— Planner 输出超过则截断
- 每个 sub-task 最多 refine ``max_refine_per_task`` 次（默认 2，即 Solver 重跑 2 轮）
- 总 LLM 调用数 ≤ ``max_total_llm_calls``（默认 30；超过抛 RuntimeError）

流程：
1. Plan：调一次 PlannerAgent，得到 sub_tasks
2. 对每个 sub_task：
   2.1 Solve：调 SolverAgent 执行
   2.2 Critique：调 CriticAgent 评审
   2.3 若 ``critic.pass=False`` 且 refine 次数未达上限：
        把 critic feedback 注入 history → 回 2.1 重跑 Solver
3. 合成最终答案（按 sub_task 顺序拼接 + 一个 "## 最终答案" 段）
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from course_agent.agent.critic import CriticAgent
from course_agent.agent.planner import PlannerAgent
from course_agent.agent.solver import SolverAgent
from course_agent.capabilities.adapters import build_default_capability_registry
from course_agent.capabilities.registry import CapabilityRegistry
from course_agent.capabilities.router import CapabilityRouter
from course_agent.core.state import AgentCallbacks
from course_agent.llm.base import BaseLLM, LLMMessage
from course_agent.logger import get_logger
from course_agent.mcp.config import MCPConfig
from course_agent.tools.registry import ToolRegistry, get_registry

_log = get_logger("Orchestrator")


class SubTaskResult(BaseModel):
    """单个 sub_task 的执行 + 评审结果."""

    sub_task: dict[str, Any]
    solver_output: str
    critic: dict[str, Any]
    refine_rounds: int = 0


class OrchestratorResult(BaseModel):
    """Orchestrator 最终执行结果."""

    final_answer: str
    plan: list[dict[str, Any]] = Field(default_factory=list)
    sub_results: list[SubTaskResult] = Field(default_factory=list)
    total_llm_calls: int = 0


class Orchestrator:
    """Plan → Solve → Critique → Refine 闭环编排器."""

    name = "Orchestrator"

    def __init__(
        self,
        llm: BaseLLM,
        registry: ToolRegistry | None = None,
        max_refine_per_task: int = 2,
        max_sub_tasks: int = 5,
        max_total_llm_calls: int = 30,
        planner_max_steps: int = 4,
        solver_max_steps: int = 8,
        critic_max_steps: int = 3,
        capability_registry: CapabilityRegistry | None = None,
        capability_router: CapabilityRouter | None = None,
        mcp_cfg: MCPConfig | None = None,
        enable_capabilities: bool = False,
    ) -> None:
        reg = registry or get_registry()
        cap_registry = (
            capability_registry
            if capability_registry is not None
            else (
                build_default_capability_registry(tool_registry=reg, mcp_cfg=mcp_cfg)
                if enable_capabilities
                else None
            )
        )
        cap_router = capability_router or (
            CapabilityRouter(cap_registry) if cap_registry is not None else None
        )
        self.planner = PlannerAgent(
            llm,
            registry=reg,
            max_steps=planner_max_steps,
            max_sub_tasks=max_sub_tasks,
            capability_router=cap_router,
        )
        self.solver = SolverAgent(
            llm,
            registry=reg,
            max_steps=solver_max_steps,
            capability_registry=cap_registry,
            capability_router=cap_router,
            mcp_cfg=mcp_cfg,
            enable_capabilities=enable_capabilities,
        )
        self.critic = CriticAgent(llm, registry=reg, max_steps=critic_max_steps)
        self.max_refine_per_task = max_refine_per_task
        self.max_sub_tasks = max_sub_tasks
        self.max_total_llm_calls = max_total_llm_calls
        # Orchestrator 本身没工具集（它只是个调度器）
        self.allowed_tools: list[str] = []

    async def arun(
        self,
        user_task: str,
        callbacks: AgentCallbacks | None = None,
    ) -> OrchestratorResult:
        """跑通 Plan → Solve → Critique → Refine 闭环."""
        total_calls = 0

        # 1. Plan
        _log.info(f"Plan: {user_task[:80]}")
        plan = await self.planner.plan(user_task)
        total_calls += 1
        plan = plan[: self.max_sub_tasks]

        # 2. Per sub_task
        sub_results: list[SubTaskResult] = []
        accumulated_history: list[LLMMessage] = []

        for st in plan:
            solver_output = ""
            critic_result: dict[str, Any] = {
                "score": 3,
                "pass": True,
                "feedback": "（未评审）",
            }
            refine_round = 0
            for refine_round in range(self.max_refine_per_task + 1):
                if total_calls >= self.max_total_llm_calls:
                    raise RuntimeError(
                        f"Orchestrator 总 LLM 调用数已达上限 "
                        f"{self.max_total_llm_calls}，强制中止以防死循环"
                    )

                _log.info(f"Solve sub_task#{st['id']} (round {refine_round})")
                solver_result = await self.solver.solve(
                    st, history=accumulated_history if accumulated_history else None,
                    callbacks=callbacks,
                )
                solver_output = solver_result.answer
                total_calls += 1

                if total_calls >= self.max_total_llm_calls:
                    critic_result = {
                        "score": 3,
                        "pass": True,
                        "feedback": "⚠️ 已达 LLM 调用上限，跳过 Critic",
                    }
                    break

                _log.info(f"Critique sub_task#{st['id']}")
                critic_result = await self.critic.critique(st, solver_output)
                total_calls += 1

                if critic_result.get("pass"):
                    break
                if refine_round == self.max_refine_per_task:
                    _log.warning(
                        f"sub_task#{st['id']} 已达 refine 上限 "
                        f"({self.max_refine_per_task})，保留当前结果"
                    )
                    break

                # 注入 critic feedback 让 solver 重跑
                accumulated_history.append(
                    LLMMessage(
                        role="system",
                        content=(
                            f"[Critic Feedback for sub-task #{st['id']}] "
                            f"{critic_result.get('feedback', '')}"
                        ),
                    )
                )

            sub_results.append(
                SubTaskResult(
                    sub_task=st,
                    solver_output=solver_output,
                    critic=critic_result,
                    refine_rounds=refine_round,
                )
            )
            # 把 solver 的输出（截断 300 字）作为后续 sub_task 的上下文
            accumulated_history.append(
                LLMMessage(
                    role="assistant",
                    content=(
                        f"[Sub-Task #{st['id']} 完成] "
                        f"{solver_output[:300]}"
                        + ("..." if len(solver_output) > 300 else "")
                    ),
                )
            )

        # 3. 合成最终答案
        final = self._synthesize(plan, sub_results)
        return OrchestratorResult(
            final_answer=final,
            plan=plan,
            sub_results=sub_results,
            total_llm_calls=total_calls,
        )

    @staticmethod
    def _synthesize(
        plan: list[dict[str, Any]], sub_results: list[SubTaskResult]
    ) -> str:
        """按 sub_task 顺序拼接 + 一个汇总段."""
        if not sub_results:
            return "（Orchestrator 未产出任何结果）"
        if len(sub_results) == 1:
            # 单 sub_task 模式：直接返回 solver 的输出，不加分段标题
            return sub_results[0].solver_output
        lines = ["## 最终答案\n"]
        for sr in sub_results:
            sid = sr.sub_task.get("id", "?")
            title = sr.sub_task.get("title", "")
            lines.append(f"### Sub-Task #{sid}：{title}\n")
            lines.append(sr.solver_output)
            score = sr.critic.get("score", "?")
            pass_ = "✅" if sr.critic.get("pass") else "❌"
            lines.append(
                f"\n> {pass_} Critic 评分：{score}/5 ｜ "
                f"反馈：{sr.critic.get('feedback', '')} ｜ "
                f"refine: {sr.refine_rounds} 轮\n"
            )
        return "\n".join(lines)


__all__ = ["Orchestrator", "OrchestratorResult", "SubTaskResult"]
