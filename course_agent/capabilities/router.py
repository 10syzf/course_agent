"""Capability Router（Task 013）.

目标：在不推翻 ToolRegistry / AgentLoop 的前提下，把 capability 收敛成
给当前 Agent 可见的“工具视图”。
"""

from __future__ import annotations

from typing import Any

from course_agent.capabilities.base import CapabilityKind, CapabilitySpec
from course_agent.capabilities.registry import CapabilityRegistry


class CapabilityRouter:
    """最小可用能力路由器."""

    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry

    def select_for_agent(
        self,
        agent_name: str,
        allowed_names: list[str] | None = None,
        *,
        include_disabled: bool = False,
    ) -> list[CapabilitySpec]:
        specs = self.registry.list_all() if include_disabled else self.registry.list_enabled()

        # Critic 继续强收口：只允许内部资料核对
        if agent_name == "Critic":
            specs = [s for s in specs if s.kind == CapabilityKind.INTERNAL_TOOL]

        # Planner 只允许内部轻量信息工具；skill/mcp 仅感知但不执行，故这里不暴露
        if agent_name == "Planner":
            specs = [s for s in specs if s.kind == CapabilityKind.INTERNAL_TOOL]

        if allowed_names is not None:
            allowed = set(allowed_names)
            specs = [s for s in specs if s.name in allowed]

        return sorted(specs, key=lambda s: (s.kind.value, s.name))

    def summarize_for_planner(
        self,
        *,
        max_items: int = 12,
    ) -> list[dict[str, Any]]:
        """给 Planner 一个轻量能力概览，仅用于建议，不用于执行."""
        items = [
            {
                "name": s.name,
                "kind": s.kind.value,
                "description": s.description,
            }
            for s in self.registry.list_enabled()
            if s.kind in (CapabilityKind.SKILL, CapabilityKind.MCP)
        ]
        return items[:max_items]


__all__ = ["CapabilityRouter"]
