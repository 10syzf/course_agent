"""MCP Adapter 单测（Task 013）."""

from __future__ import annotations

import pytest

from course_agent.capabilities import CapabilityKind
from course_agent.mcp.client import MCPClientProvider
from course_agent.mcp.config import MCPConfig, MCPServerConfig
from course_agent.mcp.mock_server import call_mock_tool, list_mock_tools


def test_mock_server_lists_tools():
    rows = list_mock_tools("demo")
    assert len(rows) == 2
    assert any(r["display_name"] == "demo/echo" for r in rows)


def test_mock_server_call_echo():
    assert call_mock_tool("mcp_demo_echo", {"text": "hello"}) == "hello"


def test_mock_server_call_keyword_extract():
    out = call_mock_tool("mcp_demo_keyword_extract", {"text": "a b c", "top_k": 2})
    assert out == "a, b"


def test_mcp_provider_disabled_returns_empty_list():
    provider = MCPClientProvider(MCPConfig(enabled=False))
    assert provider.list_capabilities() == []


def test_mcp_provider_enabled_lists_capabilities():
    provider = MCPClientProvider(
        MCPConfig(
            enabled=True,
            servers=[MCPServerConfig(name="demo", transport="mock")],
        )
    )
    rows = provider.list_capabilities()
    assert len(rows) == 2
    assert all(r.kind == CapabilityKind.MCP for r in rows)
    assert any(r.meta["display_name"] == "demo/echo" for r in rows)


@pytest.mark.asyncio
async def test_mcp_provider_call_happy_path():
    provider = MCPClientProvider(
        MCPConfig(
            enabled=True,
            servers=[MCPServerConfig(name="demo", transport="mock")],
        )
    )
    result = await provider.call("mcp_demo_echo", {"text": "hi"})
    assert result.ok is True
    assert result.output == "hi"


@pytest.mark.asyncio
async def test_mcp_provider_unknown_tool_raises():
    provider = MCPClientProvider(
        MCPConfig(
            enabled=True,
            servers=[MCPServerConfig(name="demo", transport="mock")],
        )
    )
    with pytest.raises(KeyError):
        await provider.call("mcp_demo_missing", {})


def test_non_mock_transport_currently_skipped():
    provider = MCPClientProvider(
        MCPConfig(
            enabled=True,
            servers=[MCPServerConfig(name="real", transport="stdio")],
        )
    )
    assert provider.list_capabilities() == []
