"""LangGraph 运行时：图式封装现有 Orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from course_agent.agent import Orchestrator, OrchestratorResult
from course_agent.graph import build_orchestrator_graph, draw_mermaid
from course_agent.observability.metrics import (
    reset_current_runtime_backend,
    set_current_runtime_backend,
)
from course_agent.runtime.state import make_initial_state, state_to_result


class LangGraphRuntime:
    """Task 014 LangGraph Runtime."""

    backend = "langgraph"

    def __init__(self, **kwargs: Any) -> None:
        self.llm = kwargs["llm"]
        self.checkpoint = kwargs.get("checkpoint", "memory")
        self.draw_graph = bool(kwargs.get("draw_graph", True))
        self._sqlite_saver_cm: Any | None = None
        self._callbacks: Any | None = None
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
        self._checkpointer = self._build_checkpointer()
        self._graph = build_orchestrator_graph(
            self.orchestrator,
            callbacks_getter=lambda: self._callbacks,
            checkpointer=self._checkpointer,
        )

    def _build_checkpointer(self) -> Any | None:
        checkpoint = str(self.checkpoint).strip().lower()
        if checkpoint in {"", "none", "off", "false"}:
            return None
        if checkpoint == "memory":
            from langgraph.checkpoint.memory import InMemorySaver

            return InMemorySaver()
        if checkpoint == "sqlite":
            from langgraph.checkpoint.sqlite import SqliteSaver

            root = Path(__file__).resolve().parent.parent.parent
            db_path = (root / "data" / "langgraph_checkpoint.db").resolve()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._sqlite_saver_cm = SqliteSaver.from_conn_string(str(db_path))
            return self._sqlite_saver_cm.__enter__()
        return None

    async def arun(
        self,
        user_task: str,
        callbacks: Any | None = None,
    ) -> OrchestratorResult:
        self._callbacks = callbacks
        token = set_current_runtime_backend(self.backend)
        try:
            state = await self._graph.ainvoke(
                make_initial_state(user_task, backend=self.backend),
                config={"configurable": {"thread_id": str(uuid4())}},
            )
        finally:
            self._callbacks = None
            reset_current_runtime_backend(token)
        return state_to_result(state)

    def get_graph_mermaid(self) -> str:
        return draw_mermaid(self._graph)
