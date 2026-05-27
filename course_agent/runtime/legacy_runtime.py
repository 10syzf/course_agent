"""Legacy 运行时：薄封装现有 Orchestrator."""

from __future__ import annotations

from typing import Any

from course_agent.agent import Orchestrator, OrchestratorResult
from course_agent.observability.metrics import (
    reset_current_runtime_backend,
    set_current_runtime_backend,
)


class LegacyRuntime:
    """保留 Task 012 的 legacy 编排路径."""

    backend = "legacy"

    def __init__(self, **kwargs: Any) -> None:
        self.llm = kwargs["llm"]
        self.orchestrator = Orchestrator(
            llm=kwargs["llm"],
            registry=kwargs.get("registry"),
            max_refine_per_task=kwargs.get("max_refine_per_task", 2),
            max_sub_tasks=kwargs.get("max_sub_tasks", 5),
            max_total_llm_calls=kwargs.get("max_total_llm_calls", 30),
            planner_max_steps=kwargs.get("planner_max_steps", 4),
            solver_max_steps=kwargs.get("solver_max_steps", 8),
            critic_max_steps=kwargs.get("critic_max_steps", 3),
            capability_registry=kwargs.get("capability_registry"),
            capability_router=kwargs.get("capability_router"),
            mcp_cfg=kwargs.get("mcp_cfg"),
            enable_capabilities=kwargs.get("enable_capabilities", False),
        )

    async def arun(
        self,
        user_task: str,
        callbacks: Any | None = None,
    ) -> OrchestratorResult:
        token = set_current_runtime_backend(self.backend)
        try:
            return await self.orchestrator.arun(user_task, callbacks=callbacks)
        finally:
            reset_current_runtime_backend(token)

    def get_graph_mermaid(self) -> str:
        return """flowchart TD
    START([START]) --> Planner
    Planner --> Solver
    Solver --> Critic
    Critic -->|pass| Append
    Critic -->|fail| Solver
    Append --> END([END])
"""
