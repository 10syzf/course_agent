"""双运行时选择入口."""

from __future__ import annotations

from enum import Enum
from typing import Any

from course_agent.core import AgentLoop
from course_agent.llm import create_llm
from course_agent.runtime.langgraph_runtime import LangGraphRuntime
from course_agent.runtime.legacy_runtime import LegacyRuntime
from course_agent.runtime.react_graph_runtime import ReactGraphRuntime
from course_agent.runtime.session_runtime import SessionRuntime
from course_agent.session import SessionStore
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


def create_chat_runtime(
    cfg: Any,
    *,
    llm: Any | None = None,
    registry: Any | None = None,
    backend: str | None = None,
    system_prompt: str | None = None,
    tool_names: list[str] | None = None,
    **kwargs: Any,
) -> AgentLoop | ReactGraphRuntime:
    """根据配置创建单 Agent chat runtime."""
    selected = (
        backend
        or getattr(getattr(cfg, "runtime", None), "agent_loop_backend", None)
        or RuntimeBackend.LEGACY.value
    ).strip().lower()

    llm = llm or create_llm(cfg.llm)
    registry = registry or get_registry()
    max_steps = kwargs.pop("max_steps", getattr(cfg.agent, "max_steps", 8))
    trace_dir = kwargs.pop(
        "trace_dir",
        getattr(getattr(cfg, "runtime", None), "trace_dir", "data/replays"),
    )
    prompt_dir = kwargs.pop(
        "prompt_dir",
        getattr(getattr(cfg, "runtime", None), "prompt_dir", "data/prompts"),
    )
    context_dir = kwargs.pop(
        "context_dir",
        getattr(getattr(cfg, "runtime", None), "context_dir", "data/contexts"),
    )

    if selected == RuntimeBackend.LANGGRAPH.value:
        return ReactGraphRuntime(
            llm=llm,
            registry=registry,
            tool_names=tool_names,
            max_steps=max_steps,
            system_prompt=system_prompt,
            trace_dir=trace_dir,
            prompt_dir=prompt_dir,
            context_dir=context_dir,
        )
    return AgentLoop(
        llm=llm,
        registry=registry,
        tool_names=tool_names,
        max_steps=max_steps,
        system_prompt=system_prompt,
        prompt_dir=prompt_dir,
        context_dir=context_dir,
    )


def create_session_runtime(
    cfg: Any,
    *,
    llm: Any | None = None,
    registry: Any | None = None,
    backend: str | None = None,
    system_prompt: str | None = None,
    tool_names: list[str] | None = None,
    **kwargs: Any,
) -> SessionRuntime:
    """创建带 session store 的 stateful runtime."""
    runtime = create_chat_runtime(
        cfg,
        llm=llm,
        registry=registry,
        backend=backend or RuntimeBackend.LANGGRAPH.value,
        system_prompt=system_prompt,
        tool_names=tool_names,
        **kwargs,
    )
    if not isinstance(runtime, ReactGraphRuntime):
        raise ValueError("SessionRuntime 当前仅支持 langgraph chat runtime")
    session_dir = kwargs.pop(
        "session_dir",
        getattr(getattr(cfg, "runtime", None), "session_dir", "data/sessions"),
    )
    return SessionRuntime(
        runtime=runtime,
        session_store=SessionStore(session_dir=session_dir),
    )
