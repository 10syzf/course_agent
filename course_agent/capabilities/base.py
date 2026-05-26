"""Capability 抽象层（Task 013）.

统一描述三类能力：
- internal_tool：项目内置 ToolRegistry 工具
- skill：本地高层能力封装
- mcp：外部 MCP server 暴露的能力
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class CapabilityKind(StrEnum):
    INTERNAL_TOOL = "internal_tool"
    SKILL = "skill"
    MCP = "mcp"


class CapabilitySpec(BaseModel):
    """统一能力描述."""

    name: str
    kind: CapabilityKind
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    source: str = ""
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True
    meta: dict[str, Any] = Field(default_factory=dict)


class CapabilityCallResult(BaseModel):
    """一次 capability 调用结果."""

    capability_name: str
    kind: CapabilityKind
    ok: bool = True
    output: str = ""
    error: str | None = None
    latency_ms: int = 0
    meta: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class BaseCapabilityProvider(Protocol):
    """能力提供者协议."""

    provider_name: str

    def list_capabilities(self) -> list[CapabilitySpec]:
        ...

    async def call(
        self, name: str, arguments: dict[str, Any]
    ) -> CapabilityCallResult:
        ...


__all__ = [
    "BaseCapabilityProvider",
    "CapabilityCallResult",
    "CapabilityKind",
    "CapabilitySpec",
]
