"""MCP Adapter（Task 013）.

本期只实现 mock-first 适配层：不强依赖真实 MCP server，默认可离线测试。
"""

from __future__ import annotations

import time

from course_agent.capabilities.base import CapabilityCallResult, CapabilityKind, CapabilitySpec
from course_agent.logger import get_logger
from course_agent.mcp.config import MCPConfig
from course_agent.mcp.mock_server import call_mock_tool, list_mock_tools
from course_agent.observability.metrics import track_capability_call

_log = get_logger("MCPClient")


class MCPClientProvider:
    provider_name = "mcp"

    def __init__(self, cfg: MCPConfig | None = None) -> None:
        self.cfg = cfg or MCPConfig()

    def list_capabilities(self) -> list[CapabilitySpec]:
        if not self.cfg.enabled:
            return []
        out: list[CapabilitySpec] = []
        for server in self.cfg.servers:
            if not server.enabled:
                continue
            # 本期只支持 mock transport；其它 transport 先跳过
            if server.transport != "mock":
                continue
            for t in list_mock_tools(server.name):
                out.append(
                    CapabilitySpec(
                        name=t["name"],
                        kind=CapabilityKind.MCP,
                        description=t["description"],
                        parameters=t["parameters"],
                        source=f"mcp:{server.name}",
                        meta={
                            "server_name": server.name,
                            "display_name": t.get("display_name", t["name"]),
                        },
                    )
                )
        return out

    async def call(self, name: str, arguments: dict[str, object]) -> CapabilityCallResult:
        with track_capability_call(
            capability_name=name,
            capability_kind=CapabilityKind.MCP.value,
            provider_name=self.provider_name,
        ) as rec:
            t0 = time.perf_counter()
            try:
                output = call_mock_tool(name, arguments)
            except Exception as e:  # noqa: BLE001
                rec.status = "error"
                rec.error = f"{type(e).__name__}: {str(e)[:300]}"
                raise
            latency = int((time.perf_counter() - t0) * 1000)
            return CapabilityCallResult(
                capability_name=name,
                kind=CapabilityKind.MCP,
                ok=True,
                output=output,
                latency_ms=latency,
            )


__all__ = ["MCPClientProvider"]
