"""Mock MCP server（Task 013）.

这里不实现真实协议，只提供可离线测试的能力清单与执行函数。
"""

from __future__ import annotations

from typing import Any


def list_mock_tools(server_name: str = "demo") -> list[dict[str, Any]]:
    return [
        {
            "name": f"mcp_{server_name}_echo",
            "display_name": f"{server_name}/echo",
            "description": "回显输入文本",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
        {
            "name": f"mcp_{server_name}_keyword_extract",
            "display_name": f"{server_name}/keyword_extract",
            "description": "抽取文本中的前几个关键词",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "top_k": {"type": "integer", "default": 3},
                },
                "required": ["text"],
            },
        },
    ]


def call_mock_tool(name: str, arguments: dict[str, Any]) -> str:
    if name.endswith("_echo"):
        return str(arguments.get("text", ""))
    if name.endswith("_keyword_extract"):
        text = str(arguments.get("text", "")).strip()
        top_k = max(1, min(int(arguments.get("top_k", 3)), 10))
        words = [w for w in text.replace("\n", " ").split(" ") if w]
        return ", ".join(words[:top_k]) or "（无关键词）"
    raise KeyError(f"未知 mock MCP tool: {name}")


__all__ = ["call_mock_tool", "list_mock_tools"]
