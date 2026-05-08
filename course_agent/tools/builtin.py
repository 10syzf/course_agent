"""内置工具：file_read / file_write / calculator / web_search(mock)."""

from __future__ import annotations

import ast
import operator as op
from pathlib import Path

from course_agent.tools.registry import tool

_SAFE_OPS: dict[type, object] = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Mod: op.mod,
    ast.Pow: op.pow,
    ast.FloorDiv: op.floordiv,
    ast.USub: op.neg,
    ast.UAdd: op.pos,
}


def _eval_expr(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_expr(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"不允许的常量：{node.value!r}")
    if isinstance(node, ast.BinOp):
        fn = _SAFE_OPS.get(type(node.op))
        if fn is None:
            raise ValueError(f"不允许的运算符：{type(node.op).__name__}")
        return fn(_eval_expr(node.left), _eval_expr(node.right))  # type: ignore[operator]
    if isinstance(node, ast.UnaryOp):
        fn = _SAFE_OPS.get(type(node.op))
        if fn is None:
            raise ValueError(f"不允许的一元运算符：{type(node.op).__name__}")
        return fn(_eval_expr(node.operand))  # type: ignore[operator]
    raise ValueError(f"不允许的语法节点：{type(node).__name__}")


@tool(name="calculator", description="计算一个数学表达式，支持 + - * / % ** 和括号")
def calculator(expression: str) -> str:
    """安全地求值数学表达式."""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_expr(tree)
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算失败：{e}"


@tool(name="file_read", description="读取本地文件内容（UTF-8）")
def file_read(path: str) -> str:
    """读取文件并返回字符串内容."""
    p = Path(path).expanduser()
    if not p.exists():
        return f"文件不存在：{p}"
    if not p.is_file():
        return f"路径不是文件：{p}"
    try:
        return p.read_text(encoding="utf-8")
    except Exception as e:
        return f"读取失败：{e}"


@tool(name="file_write", description="将内容写入本地文件（UTF-8，会自动创建父目录）")
def file_write(path: str, content: str) -> str:
    """把内容写入到指定文件."""
    p = Path(path).expanduser()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"已写入 {p}，长度 {len(content)} 字符"
    except Exception as e:
        return f"写入失败：{e}"


@tool(name="web_search", description="在网络上搜索关键词，返回前若干条结果（当前为 Mock 实现）")
def web_search(query: str, top_k: int = 3) -> str:
    """Mock 的网页搜索，后续里程碑会替换为真实 DuckDuckGo/Bing."""
    fake_results = [
        {
            "title": f"[Mock] 关于「{query}」的结果 #{i + 1}",
            "url": f"https://example.com/search?q={query}&n={i + 1}",
            "snippet": f"这是针对 \"{query}\" 的第 {i + 1} 条占位摘要。",
        }
        for i in range(max(1, min(top_k, 5)))
    ]
    lines = [
        f"{i + 1}. {r['title']}\n   {r['url']}\n   {r['snippet']}"
        for i, r in enumerate(fake_results)
    ]
    return "\n".join(lines)
