"""双运行时选择入口."""

from __future__ import annotations

from enum import Enum
from typing import Any

from course_agent.llm import create_llm
from course_agent.runtime.langgraph_runtime import LangGraphRuntime
from course_agent.runtime.legacy_runtime import LegacyRuntime
from course_agent.tools import get_registry


class RuntimeBackend(Enum):
    LEGACY = "legacy"
    LANGGRAPH = "langgraph"


def create_runtime(
    cfg: Any,
    *,
    llm: Any | None = None,
    registry: Any | None = None,
    backend: str | None = None,
    enable_capabilities: bool = False,
    **kwargs: Any,
) -> LegacyRuntime | LangGraphRuntime:
    """根据配置创建统一运行时对象."""
    selected = (
        backend
        or getattr(getattr(cfg, "runtime", None), "backend", None)
        or RuntimeBackend.LEGACY.value
    ).strip().lower()

    llm = llm or create_llm(cfg.llm)
    registry = registry or get_registry()

    common: dict[str, Any] = {
        "llm": llm,
        "registry": registry,
        "max_refine_per_task": kwargs.pop("max_refine_per_task", 2),
        "max_sub_tasks": kwargs.pop("max_sub_tasks", 5),
        "max_total_llm_calls": kwargs.pop("max_total_llm_calls", 30),
        "planner_max_steps": kwargs.pop("planner_max_steps", 4),
        "solver_max_steps": kwargs.pop(
            "solver_max_steps", getattr(cfg.agent, "max_steps", 8)
        ),
        "critic_max_steps": kwargs.pop("critic_max_steps", 3),
        "mcp_cfg": kwargs.pop("mcp_cfg", getattr(cfg, "mcp", None)),
        "enable_capabilities": enable_capabilities,
    }
    common.update(kwargs)

    if selected == RuntimeBackend.LANGGRAPH.value:
        return LangGraphRuntime(**common)
    return LegacyRuntime(**common)
