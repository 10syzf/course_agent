"""Capability Provider 适配器（Task 013）."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from course_agent.capabilities.base import (
    CapabilityCallResult,
    CapabilityKind,
    CapabilitySpec,
)
from course_agent.capabilities.registry import CapabilityRegistry
from course_agent.logger import get_logger
from course_agent.mcp.client import MCPClientProvider
from course_agent.mcp.config import MCPConfig
from course_agent.observability.metrics import track_capability_call
from course_agent.skills.runtime import LocalSkillProvider
from course_agent.tools import Tool, ToolRegistry, get_registry

_log = get_logger("CapabilityAdapters")


class InternalToolProvider:
    """把 ToolRegistry 包装成 Capability Provider."""

    provider_name = "tool_registry"

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def list_capabilities(self) -> list[CapabilitySpec]:
        out = []
        for t in self.registry.all():
            out.append(
                CapabilitySpec(
                    name=t.name,
                    kind=CapabilityKind.INTERNAL_TOOL,
                    description=t.description,
                    parameters=t.parameters,
                    source="tool_registry",
                )
            )
        return out

    async def call(
        self, name: str, arguments: dict[str, Any]
    ) -> CapabilityCallResult:
        tool = self.registry.get(name)
        with track_capability_call(
            capability_name=name,
            capability_kind=CapabilityKind.INTERNAL_TOOL.value,
            provider_name=self.provider_name,
        ) as rec:
            t0 = time.perf_counter()
            try:
                if asyncio.iscoroutinefunction(tool.func):
                    result = await tool.func(**arguments)
                else:
                    result = await asyncio.to_thread(tool.run, **arguments)
            except Exception as e:  # noqa: BLE001
                rec.status = "error"
                rec.error = f"{type(e).__name__}: {str(e)[:300]}"
                raise
            latency = int((time.perf_counter() - t0) * 1000)
            return CapabilityCallResult(
                capability_name=name,
                kind=CapabilityKind.INTERNAL_TOOL,
                ok=True,
                output=str(result),
                latency_ms=latency,
            )


class CapabilityToolProvider:
    """把任意 CapabilityRegistry 暴露成 ToolRegistry 兼容视图."""

    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry

    @staticmethod
    def _make_func(
        reg: CapabilityRegistry, spec: CapabilitySpec
    ) -> Any:
        def _wrapped(**kwargs: Any) -> str:
            async def _run() -> str:
                result = await reg.call(spec.name, kwargs)
                if not result.ok:
                    raise RuntimeError(result.error or f"{spec.name} 执行失败")
                return result.output

            return asyncio.run(_run())

        return _wrapped

    def to_tool_registry(self, selected: list[CapabilitySpec]) -> ToolRegistry:
        reg = ToolRegistry()
        for spec in selected:
            reg.register(
                Tool(
                    name=spec.name,
                    description=spec.description,
                    parameters=spec.parameters,
                    func=self._make_func(self.registry, spec),
                )
            )
        return reg


def build_default_capability_registry(
    *,
    tool_registry: ToolRegistry | None = None,
    mcp_cfg: MCPConfig | None = None,
) -> CapabilityRegistry:
    cap = CapabilityRegistry()
    cap.register_provider(InternalToolProvider(tool_registry or get_registry()))
    cap.register_provider(LocalSkillProvider())
    cap.register_provider(MCPClientProvider(mcp_cfg or MCPConfig()))
    return cap


def build_capability_tool_registry(
    providers: CapabilityRegistry,
    selected: list[CapabilitySpec],
) -> ToolRegistry:
    return CapabilityToolProvider(providers).to_tool_registry(selected)


__all__ = [
    "CapabilityToolProvider",
    "InternalToolProvider",
    "build_capability_tool_registry",
    "build_default_capability_registry",
]
