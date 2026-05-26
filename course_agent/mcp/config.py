"""MCP 配置模型（Task 013）."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    name: str
    transport: str = "mock"
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    timeout_s: int = 15
    enabled: bool = True


class MCPConfig(BaseModel):
    enabled: bool = False
    servers: list[MCPServerConfig] = Field(default_factory=list)


__all__ = ["MCPConfig", "MCPServerConfig"]
