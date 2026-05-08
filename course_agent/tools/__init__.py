"""工具系统：Registry + @tool 装饰器 + 内置工具."""

from course_agent.tools import builtin  # noqa: F401  确保内置工具注册
from course_agent.tools.registry import Tool, ToolRegistry, get_registry, tool

__all__ = ["Tool", "ToolRegistry", "get_registry", "tool"]
