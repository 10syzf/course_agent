"""Tool Registry：装饰器注册 + JSON Schema 自动生成."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, get_type_hints

_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


@dataclass
class Tool:
    """工具描述."""

    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., Any]

    def to_openai_schema(self) -> dict[str, Any]:
        """转换成 OpenAI function-calling 所需的 schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def run(self, **kwargs: Any) -> Any:
        """执行工具函数."""
        return self.func(**kwargs)


class ToolRegistry:
    """工具注册中心."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, t: Tool) -> None:
        if t.name in self._tools:
            raise ValueError(f"Tool 已存在: {t.name}")
        self._tools[t.name] = t

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"Tool 未注册: {name}")
        return self._tools[name]

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def to_openai_schemas(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        tools = [self._tools[n] for n in names] if names else self.all()
        return [t.to_openai_schema() for t in tools]


_global_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """获取全局 Tool Registry."""
    return _global_registry


def _build_schema(func: Callable[..., Any]) -> dict[str, Any]:
    """从函数签名和 type hints 生成 JSON Schema."""
    sig = inspect.signature(func)
    hints = get_type_hints(func)

    properties: dict[str, Any] = {}
    required: list[str] = []

    for pname, param in sig.parameters.items():
        if pname == "self":
            continue
        py_type = hints.get(pname, str)
        origin = getattr(py_type, "__origin__", py_type)
        json_type = _TYPE_MAP.get(origin, "string")

        properties[pname] = {"type": json_type}
        if param.default is inspect.Parameter.empty:
            required.append(pname)
        else:
            properties[pname]["default"] = param.default

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def tool(
    name: str | None = None,
    description: str | None = None,
    registry: ToolRegistry | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """将普通函数注册为工具."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        tool_name = name or func.__name__
        doc = description or (func.__doc__ or "").strip().split("\n")[0] or tool_name
        schema = _build_schema(func)

        t = Tool(name=tool_name, description=doc, parameters=schema, func=func)
        target = registry or _global_registry
        target.register(t)
        return func

    return decorator
